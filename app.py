from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import random
import string

app = Flask(__name__)
# Permitir conexiones externas (desde GitHub Pages)
socketio = SocketIO(app, cors_allowed_origins="*")

# Estructuras de datos en memoria
users = {}  
rooms = {}  
# Los 7 caballos competidores
horses = ['Rojo', 'Azul', 'Verde', 'Amarillo', 'Naranja', 'Morado', 'Blanco']

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
    emit('room_response', {'room': room_code, 'is_creator': True})

@socketio.on('join_room')
def handle_join_room(data):
    room_code = data['room'].upper().strip()
    
    if room_code in rooms:
        join_room(room_code)
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
        # VALIDACIÓN: Evitar múltiples apuestas por el mismo usuario
        if nick in rooms[room]['bets']:
            emit('error_msg', {'msg': 'Ya realizaste una apuesta para esta carrera.'}, to=request.sid)
        else:
            rooms[room]['bets'][nick] = color
            # Avisar a toda la sala
            emit('bet_placed', {'nick': nick, 'color': color}, to=room)
            # Avisar SOLO al usuario para bloquear sus botones
            emit('bet_accepted', {'color': color}, to=request.sid)

@socketio.on('start_race')
def handle_start(data):
    room = data['room'].upper()
    if room in rooms:
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
    
    # Reiniciar sala para la próxima carrera
    rooms[room]['active'] = False
    rooms[room]['bets'] = {}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
