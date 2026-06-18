from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import random
import string

app = Flask(__name__)
# Permitir conexiones externas (como GitHub Pages)
socketio = SocketIO(app, cors_allowed_origins="*")

# Estructuras de datos en memoria
users = {}  # Guarda correspondencia -> request.sid: nickname
rooms = {}  # Guarda el estado -> código: { 'creator': sid, 'bets': {}, 'active': False }
horses = ['Rojo', 'Azul', 'Verde', 'Amarillo']

def generate_room_code():
    """Genera un código único de 5 letras/números en mayúsculas"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if code not in rooms:
            return code

@socketio.on('set_nick')
def handle_nick(data):
    users[request.sid] = data['nick']
    emit('chat_msg', {'user': 'Sistema', 'msg': f"{data['nick']} ha entrado al lobby."}, broadcast=True)

@socketio.on('chat_msg')
def handle_chat(msg):
    nick = users.get(request.sid, 'Anónimo')
    emit('chat_msg', {'user': nick, 'msg': msg['text']}, broadcast=True)

@socketio.on('create_room')
def handle_create_room():
    room_code = generate_room_code()
    rooms[room_code] = {
        'creator': request.sid,
        'bets': {},
        'active': False
    }
    join_room(room_code)
    # Le indicamos al cliente que él creó la sala
    emit('room_response', {'room': room_code, 'is_creator': True})
    
    nick = users.get(request.sid, 'Anónimo')
    print(f"Sala {room_code} creada por {nick}")

@socketio.on('join_room')
def handle_join_room(data):
    room_code = data['room'].upper().strip()
    
    if room_code in rooms:
        join_room(room_code)
        # Verificamos si por algún motivo es el creador reconectándose o un espectador
        is_creator = (rooms[room_code]['creator'] == request.sid)
        
        emit('room_response', {'room': room_code, 'is_creator': is_creator})
        
        nick = users.get(request.sid, 'Anónimo')
        emit('chat_msg', {'user': 'Sistema', 'msg': f"{nick} se ha unido como espectador."}, to=room_code)
    else:
        emit('error_msg', {'msg': 'El código de sala no existe.'})

@socketio.on('place_bet')
def handle_bet(data):
    room = data['room'].upper()
    color = data['color']
    nick = users.get(request.sid, 'Anónimo')
    
    if room in rooms and not rooms[room]['active']:
        rooms[room]['bets'][nick] = color
        emit('bet_placed', {'nick': nick, 'color': color}, to=room)

@socketio.on('start_race')
def handle_start(data):
    room = data['room'].upper()
    if room in rooms:
        # VALIDACIÓN CRÍTICA: ¿El que presiona el botón es realmente el dueño?
        if rooms[room]['creator'] == request.sid:
            if not rooms[room]['active']:
                rooms[room]['active'] = True
                emit('race_started', to=room)
                socketio.start_background_task(run_race, room)
        else:
            emit('error_msg', {'msg': 'No tienes permisos de administrador.'})

def run_race(room):
    progress = {h: 0 for h in horses}
    winner = None
    
    while not winner:
        socketio.sleep(0.4)
        for h in horses:
            progress[h] += random.randint(3, 14)
            if progress[h] >= 100:
                winner = h
                
        socketio.emit('race_update', progress, to=room)
    
    winners = [nick for nick, color in rooms[room]['bets'].items() if color == winner]
    socketio.emit('race_finished', {'winner': winner, 'bet_winners': winners}, to=room)
    
    rooms[room]['active'] = False
    rooms[room]['bets'] = {}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
