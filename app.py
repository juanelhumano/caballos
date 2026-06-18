from flask import Flask
from flask_socketio import SocketIO, emit, join_room
import random

app = Flask(__name__)
# Permitir que tu frontend en GitHub Pages se conecte
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

users = {}
rooms = {}
horses = ['Rojo', 'Azul', 'Verde', 'Amarillo']

@socketio.on('set_nick')
def handle_nick(data):
    users[data['id']] = data['nick']
    emit('chat_msg', {'user': 'Sistema', 'msg': f"{data['nick']} ha entrado al lobby."}, broadcast=True)

@socketio.on('chat_msg')
def handle_chat(msg):
    nick = users.get(msg['id'], 'Anónimo')
    emit('chat_msg', {'user': nick, 'msg': msg['text']}, broadcast=True)

@socketio.on('join_room')
def handle_join_room(data):
    room = data['room']
    join_room(room)
    if room not in rooms:
        rooms[room] = {'bets': {}, 'active': False}
    emit('room_joined', {'room': room}, to=data['id'])

@socketio.on('place_bet')
def handle_bet(data):
    room = data['room']
    color = data['color']
    nick = users.get(data['id'], 'Anónimo')
    
    if room in rooms and not rooms[room]['active']:
        rooms[room]['bets'][nick] = color
        emit('bet_placed', {'nick': nick, 'color': color}, to=room)

@socketio.on('start_race')
def handle_start(data):
    room = data['room']
    if room in rooms and not rooms[room]['active']:
        rooms[room]['active'] = True
        emit('race_started', to=room)
        # Iniciar la carrera en un hilo de fondo
        socketio.start_background_task(run_race, room)

def run_race(room):
    progress = {h: 0 for h in horses}
    winner = None
    
    while not winner:
        socketio.sleep(0.5) # Pausa de medio segundo por "tick"
        for h in horses:
            progress[h] += random.randint(2, 12) # Avance aleatorio
            if progress[h] >= 100:
                winner = h
                
        socketio.emit('race_update', progress, to=room)
    
    # Evaluar ganadores de apuestas
    winners = [nick for nick, color in rooms[room]['bets'].items() if color == winner]
    socketio.emit('race_finished', {'winner': winner, 'bet_winners': winners}, to=room)
    
    # Reiniciar sala
    rooms[room]['active'] = False
    rooms[room]['bets'] = {}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
