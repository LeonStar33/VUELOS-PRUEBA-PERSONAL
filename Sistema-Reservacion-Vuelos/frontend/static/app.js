const $ = s => document.querySelector(s);
let csrf = '',
    user = null,
    flights = [],
    bookings = [],
    active = null,
    offset = 0,
    busy = false;
const tripChoices = {},
    paymentChoices = {};
const money = n => new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN'
}).format(n / 100);
const names = {
    adult: 'Adulto',
    child: 'Niño',
    senior: 'Tercera edad',
    holding: 'Seleccionando',
    checkout: 'Pendiente de compra',
    paid: 'Confirmada',
    expired: 'Vencida',
    cancelled: 'Cancelada'
};

function msg(s) {
    $('#message').textContent = s;
}
async function api(url, data) {
    const res = await fetch(url, {
        method: data === undefined ? 'GET' : 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
        },
        body: data === undefined ? undefined : JSON.stringify(data)
    });
    const v = await res.json();
    if (!res.ok) throw Error(v.error || 'No se pudo completar la operación.');
    return v;
}

function el(tag, text, cls) {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
}

function action(text, fn, cls) {
    const b = el('button', text, cls);
    b.onclick = () => perform(fn);
    return b;
}
async function perform(fn) {
    if (busy) return;
    busy = true;
    try {
        await fn();
    } catch (e) {
        msg(e.message);
    } finally {
        busy = false;
    }
}
async function session() {
    const s = await api('/api/session');
    csrf = s.csrf;
    user = s.user;
    offset = s.now * 1000 - Date.now();
    $('#account').textContent = user ? user.name : 'Entrar / Registrarme';
    $('#logout').hidden = !user;
    $('#guest').hidden = !!user;
}

function renderFlights() {
    const target = $('#flights');
    target.replaceChildren();
    for (const f of flights.filter(f => f.destination.toLowerCase().includes($('#search').value.toLowerCase()))) {
        const c = el('article', undefined, 'card');
        c.append(el('span', `${f.kind} · ${f.available} disponibles`, 'tag'), el('h3', f.destination), el('div', `${f.id} · 08 nov · ${f.departure.slice(11,16)}`, 'code'), el('p', 'Desde'), el('div', money(Math.min(f.adult, f.child, f.senior)), 'price'));
        const fares = el('div', undefined, 'fares');
        for (const [key, label] of [
                ['adult', 'Adulto'],
                ['child', 'Niño'],
                ['senior', 'Tercera edad'],
                ['first', 'Primera clase']
            ]) fares.append(el('p', `${label}: ${money(f[key])}`));
        c.append(fares);
        const label = el('label', 'Tipo de viaje');
        const select = el('select');
        select.add(new Option('Sencillo', 'oneway'));
        select.add(new Option(`Ida y vuelta${f.discount?' · 20% descuento':''}`, 'roundtrip'));
        select.value = tripChoices[f.id] || 'oneway';
        select.onchange = () => {
            tripChoices[f.id] = select.value;
        };
        label.append(select);
        c.append(label, action('Elegir asientos →', async () => {
            if (!user) {
                $('#auth').hidden = false;
                $('#auth').scrollIntoView();
                return;
            }
            const b = await api('/api/bookings', {
                flight: f.id,
                trip: select.value
            });
            active = b.id;
            $('#quantity').value = 1;
            await refresh();
            $('#selection').scrollIntoView();
        }));
        target.append(c);
    }
}
async function refresh() {
    flights = await api('/api/flights');
    renderFlights();
    if (user) {
        const r = await api('/api/bookings');
        bookings = r.bookings;
        offset = r.now * 1000 - Date.now();
        renderBookings();
    } else {
        $('#bookings').replaceChildren();
    }
    await renderSeats();
}

function renderBookings() {
    const target = $('#bookings');
    target.replaceChildren();
    for (const b of bookings) {
        const c = el('article', undefined, 'booking');
        c.append(el('span', names[b.status], 'tag'), el('h3', `${b.destination} · ${b.flight_id}`), el('p', `${b.trip==='oneway'?'Sencillo':'Ida y vuelta'} · Asientos: ${b.tickets.map(t=>t.seat).join(', ')||'sin seleccionar'}`), el('p', `Total: ${money(b.total??b.tickets.reduce((n,t)=>n+t.amount,0))}`));
        const actions = el('div', undefined, 'actions');
        if (b.status === 'holding') {
            actions.append(action('Continuar selección', async () => {
                active = b.id;
                $('#quantity').value = Math.max(1, b.tickets.length);
                await renderSeats();
                $('#selection').scrollIntoView();
            }));
        }
        if (b.status === 'checkout') {
            const timer = el('p');
            timer.dataset.expires = b.expires;
            c.append(timer);
            const label = el('label', 'Método de pago simulado');
            const method = el('select');
            method.add(new Option('Efectivo', 'efectivo'));
            method.add(new Option('Tarjeta (sin datos bancarios)', 'tarjeta'));
            method.value = paymentChoices[b.id] || 'efectivo';
            method.onchange = () => {
                paymentChoices[b.id] = method.value;
            };
            label.append(method);
            c.append(label);
            actions.append(action('Confirmar compra simulada', async () => {
                const r = await api(`/api/bookings/${b.id}/pay`, {
                    method: method.value
                });
                msg('Compra simulada confirmada. ' + ({
                    enviado: 'Correo enviado.',
                    no_configurado: 'SMTP no configurado: descarga tu comprobante.',
                    fallo: 'Falló el correo; tu compra está guardada.',
                    ya_procesado: 'Esta compra ya estaba confirmada.'
                } [r.email]));
                await refresh();
            }));
        }
        if (['holding', 'checkout'].includes(b.status)) actions.append(action('Cancelar reserva', async () => {
            await api(`/api/bookings/${b.id}/cancel`, {});
            await refresh();
        }, 'secondary'));
        if (b.status === 'paid') {
            const a = el('a', 'Descargar comprobante', 'button');
            a.href = `/api/bookings/${b.id}/receipt`;
            actions.append(a);
        }
        c.append(actions);
        target.append(c);
    }
    tick();
}
async function renderSeats() {
    const b = bookings.find(b => b.id === active && b.status === 'holding');
    $('#selection').hidden = !b;
    if (!b) return;
    $('#selection-title').textContent = `${b.destination} · ${b.flight_id}`;
    $('#timer').dataset.expires = b.expires;
    const seats = await api(`/api/flights/${b.flight_id}/seats`);
    const target = $('#seats');
    target.replaceChildren();
    for (const [cabin, label] of [
            ['first', 'Primera clase · 1–10'],
            ['tourist', 'Turista · 11–30']
        ]) {
        target.append(el('h3', label));
        const grid = el('div', undefined, 'seatgrid');
        for (const s of seats.filter(s => s.cabin === cabin)) {
            const own = b.tickets.some(t => t.seat === s.number);
            const button = action(String(s.number), async () => {
                if (!own && b.tickets.length >= Number($('#quantity').value)) throw Error('Ya elegiste el número de boletos indicado. Auméntalo para seleccionar más.');
                await api(`/api/bookings/${b.id}/seats`, {
                    seat: s.number,
                    category: 'adult',
                    remove: own
                });
                await refresh();
            }, `seat ${own?'mine':s.state}`);
            button.disabled = s.state !== 'available' && !own;
            button.setAttribute('aria-label', `Asiento ${s.number}, ${own?'seleccionado':s.state==='available'?'disponible':'ocupado'}`);
            button.setAttribute('aria-pressed', String(own));
            grid.append(button);
        }
        target.append(grid);
    }
    const passengers = $('#passengers');
    passengers.replaceChildren();
    if (b.tickets.length) passengers.append(el('h3', 'Categoría de cada boleto'));
    for (const ticket of b.tickets) {
        const row = el('div', undefined, 'passenger-row');
        const label = el('label', `Asiento ${ticket.seat} · ${ticket.seat <= 10 ? 'Primera clase' : 'Turista'}`);
        const category = el('select');
        category.setAttribute('aria-label', `Categoría del asiento ${ticket.seat}`);
        for (const value of ['adult', 'child', 'senior']) category.add(new Option(names[value], value));
        category.value = ticket.category;
        category.onchange = () => {
            const value = category.value;
            perform(async () => {
                try {
                    await api(`/api/bookings/${b.id}/seats`, {seat: ticket.seat, category: value});
                    await refresh();
                } catch (error) {
                    category.value = ticket.category;
                    throw error;
                }
            });
        };
        label.append(category);
        row.append(label, el('strong', money(ticket.amount)));
        passengers.append(row);
    }
    $('#selected-total').textContent = `${b.tickets.length} seleccionados · ${money(b.tickets.reduce((n,t)=>n+t.amount,0))}`;
    tick();
}

function tick() {
    document.querySelectorAll('[data-expires]').forEach(n => {
        const s = Math.max(0, Math.ceil(Number(n.dataset.expires) - (Date.now() + offset) / 1000));
        n.textContent = s ? `Tiempo restante: ${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}` : 'Tiempo agotado. Actualizando disponibilidad…';
    });
}
$('#account').onclick = () => {
    $('#auth').hidden = !$('#auth').hidden;
};
$('#logout').onclick = () => perform(async () => {
    await api('/api/logout', {});
    active = null;
    bookings = [];
    await session();
    await refresh();
});
$('#authform').onsubmit = e => {
    e.preventDefault();
    perform(async () => {
        await api('/api/login', {
            email: $('#email').value,
            password: $('#password').value
        });
        $('#password').value = '';
        await session();
        $('#auth').hidden = true;
        msg('Sesión iniciada. Ya puedes reservar.');
        await refresh();
    });
};
$('#register').onclick = () => perform(async () => {
    if (!$('#authform').reportValidity()) return;
    await api('/api/register', {
        name: $('#name').value,
        email: $('#email').value,
        password: $('#password').value
    });
    msg('Cuenta creada. Presiona Iniciar sesión.');
});
$('#search').oninput = renderFlights;
$('#checkout').onclick = () => perform(async () => {
    const b = bookings.find(b => b.id === active);
    if (!b || b.tickets.length !== Number($('#quantity').value)) throw Error('Selecciona exactamente el número de boletos indicado.');
    await api(`/api/bookings/${active}/checkout`, {});
    msg('Tienes 15 minutos para confirmar la compra simulada.');
    await refresh();
    $('#my').scrollIntoView();
});
setInterval(tick, 1000);
setInterval(() => {
    if (!busy && !document.activeElement?.matches('select, input')) perform(refresh);
}, 5000);
perform(async () => {
    await session();
    await refresh();
});
