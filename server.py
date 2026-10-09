"""Flash Ogiri - lightweight multiplayer game server.
Run: pip install -r requirements.txt && python server.py
Python 3.10+ / aiohttp. All rooms are kept in memory.
"""
import asyncio
import json
import os
import random
import re
import secrets
import time
from collections import Counter
from pathlib import Path

from aiohttp import ClientSession, WSMsgType, web

ROOT = Path(__file__).resolve().parent
PORT = int(os.getenv('PORT', '8080'))
# Answerers automatically rotate after exactly 60 seconds (server authoritative).
# The environment overrides are intended only for accelerated integration tests.
TURN_SECONDS = int(os.getenv('OGIRI_TURN_SECONDS', '60'))
SECONDS_TO_ANSWER = int(os.getenv('OGIRI_QUESTION_SECONDS', '5'))
REVEAL_SECONDS = float(os.getenv('OGIRI_REVEAL_SECONDS', '1.25'))
CHANGEOVER_SECONDS = float(os.getenv('OGIRI_CHANGEOVER_SECONDS', '3'))
SUCCESS_POINTS = 10
MISS_POINTS = -5
QUESTION_POINTS = 5
MAX_PLAYERS = 16
ROOMS = {}

BANK = {
    '学校': [
        'こんな校長先生は嫌だ。どんな人？', '絶対に卒業できない学校。何が起こる？', '給食の新メニューに生徒が騒然。何が出た？',
        '遅刻の言い訳で先生が拍手。何と言った？', '全校朝礼が急にバズった理由は？', '教科書の最後のページに書いてあった衝撃の一言は？',
        'テストの最終問題がまさかの内容。何？', '修学旅行の行き先が変すぎる。どこ？', '文化祭で大炎上した屋台の名前は？',
        'この学校の校則、絶対おかしい。どんな校則？', '先生が突然ラップで授業を始めた理由は？', '新任教師の自己紹介、最初の一言は？'
    ],
    '日常': [
        'こんなコンビニは二度と行かない。なぜ？', '目覚まし時計が朝から説教。何と言った？', 'エレベーターに謎のボタンが追加。何用？',
        '宅配便の人が持ってきた予想外のものは？', '未来の自動販売機に売っている変なものは？', '冷蔵庫を開けたら食材たちが会議中。議題は？',
        '世界一気まずいエレベーター内のアナウンスとは？', '絶対に当たりたくない天気予報とは？', '人生で一度は押してみたいボタン。何が起きる？',
        '自転車が突然しゃべりだした。第一声は？', '満員電車で誰もが二度見した光景とは？', 'レシートの一番下に書かれていた一言とは？'
    ],
    'ゲーム': [
        'ラスボスが戦う前にしたお願いとは？', '絶対に売れないゲームのタイトルは？', 'ゲームのチュートリアルが長すぎる。何を教えている？',
        '勇者が冒険を辞めたしょうもない理由とは？', 'NPCがプレイヤーに怒った。理由は？', 'ゲームのアップデートで追加された謎機能とは？',
        '攻略サイトに載っていた最悪の裏ワザとは？', 'ポーションの新しい副作用とは？', '最弱のモンスターの意外な必殺技とは？',
        '冒険者ギルドの求人票に書かれた不安な一文とは？', 'レベル100なのに誰にも尊敬されない理由は？', '宝箱を開けた勇者が絶句。中身は？'
    ],
    '恋愛': [
        '告白の場で絶対に言ってはいけない一言とは？', 'このデート、開始3秒で失敗。何があった？', 'ラブレターの最後に書かれた予想外の一言とは？',
        '恋愛相談AIが突然匙を投げた理由とは？', 'カップル専用アプリの最悪の通知とは？', '初デートの持ち物が変すぎる。何？',
        'プロポーズの演出が大失敗。その内容は？', 'こんなマッチングアプリは嫌だ。どんなもの？', '失恋ソングのタイトルにしてはいけない言葉とは？',
        'カップルのケンカを止めた意外なものとは？'
    ],
    '意味不明': [
        'もしも月がアルバイトを始めたら、職種は？', 'カニが人類に宣戦布告。最初の要求は？', '宇宙人が地球旅行で星1評価を付けた理由とは？',
        '突然しゃべりだした靴下の第一声とは？', '透明人間が一番困っていることとは？', '神様がうっかり押してしまったボタンとは？',
        'タイムマシンに貼ってある注意書きとは？', 'ドラゴンが開いた喫茶店の名物メニューとは？', '忍者が絶対にバレる理由とは？',
        '異世界転生したらまさかの職業。何？', '恐竜が現代に来て驚いたしょうもないこととは？', '世界最後の日に発表されたどうでもいいニュースとは？'
    ],
    'AI・未来': [
        'AIが人間への反乱を中止した理由とは？', 'ロボットが有給休暇を申請。何をする？', '2100年の小学校で禁止されているものは？',
        '未来のスマートフォンに追加された意味不明な機能とは？', 'AI面接官が応募者を全員落とした理由とは？', 'ロボット掃除機が家出した理由とは？',
        '未来のニュースキャスターが謝罪した理由とは？', 'AIが俳句を読んだら怒られた。どんな句？', '未来のコンビニ店員の謎の口癖とは？',
        '人類が火星に着いて最初に文句を言ったこととは？'
    ]
}
GENRES = list(BANK)


def clean(value, length=100):
    if not isinstance(value, str):
        return ''
    return re.sub(r'[\x00-\x1f\x7f]', ' ', value).strip()[:length]


def timestamp():
    return int(time.time() * 1000)


def fresh_code():
    while True:
        code = str(random.randint(100000, 999999))
        if code not in ROOMS:
            return code


def public_state(room, player_id):
    players = [{'id': x['id'], 'name': x['name'], 'score': x['score'], 'online': x.get('ws') is not None}
               for x in room['players']]
    index = room['turn_index']
    return {
        'type': 'state', 'serverNow': timestamp(), 'room': room['code'], 'you': player_id,
        'isHost': room['host'] == player_id, 'hostId': room['host'],
        'phase': room['phase'], 'players': players,
        'turnIndex': index, 'answererId': room['players'][index]['id'] if index < len(room['players']) else None,
        'questionIndex': room['question_index'], 'turnSeconds': TURN_SECONDS, 'answerSeconds': SECONDS_TO_ANSWER,
        'queueCount': len(room['queue']), 'totalQuestions': room['total_questions'],
        'current': room['current'], 'deadline': room['deadline'],
        'turnDeadline': room['turn_deadline'], 'nextStartAt': room['next_start_at'],
        'genres': GENRES, 'hasAI': bool(os.getenv('OPENAI_API_KEY')),
        'result': room['result'],
        'lastError': None
    }


async def write(ws, payload):
    try:
        await ws.send_json(payload)
    except (ConnectionResetError, RuntimeError):
        pass


async def emit(room):
    for p in room['players']:
        if p.get('ws') is not None:
            await write(p['ws'], public_state(room, p['id']))


async def fail(ws, message):
    await write(ws, {'type': 'error', 'message': message})


def find_player(room, player_id):
    return next((p for p in room['players'] if p['id'] == player_id), None)


def fallback(room):
    available = [(genre, q) for genre, arr in BANK.items() for q in arr if q not in room['used_bank']]
    if not available:
        room['used_bank'].clear()
        available = [(genre, q) for genre, arr in BANK.items() for q in arr]
    genre, prompt = random.choice(available)
    room['used_bank'].add(prompt)
    return {'text': prompt, 'authorId': None, 'authorName': '自動出題', 'kind': 'auto', 'genre': genre}


def select_question(room):
    responder = room['players'][room['turn_index']]['id']
    # People cannot ask their own questions. Prefer audience submissions over fallback.
    eligible = [i for i, item in enumerate(room['queue']) if item['authorId'] != responder]
    if eligible:
        index = random.choice(eligible)
        item = room['queue'].pop(index)
        author = find_player(room, item['authorId'])
        if author:
            author['score'] += QUESTION_POINTS
        return item
    return fallback(room)


async def begin_turn(room):
    """Start one person's 60-second sprint; the server runs the entire rotation."""
    if room['phase'] not in ('lobby', 'intermission'):
        return
    room['question_index'] = 0
    room['turn_serial'] += 1
    turn_serial = room['turn_serial']
    room['next_start_at'] = None
    room['turn_deadline'] = timestamp() + TURN_SECONDS * 1000
    room['phase'] = 'turn_wait'
    asyncio.create_task(end_turn_at(room, turn_serial))
    await issue_question(room)


async def issue_question(room):
    if room['phase'] not in ('turn_wait', 'reveal'):
        return
    # Do not issue a question if the player cannot receive the full five seconds.
    # The server keeps the current player active until their exact minute expires.
    if timestamp() + SECONDS_TO_ANSWER * 1000 > room['turn_deadline']:
        room['phase'] = 'turn_wait'
        room['current'] = None
        room['deadline'] = None
        room['serial'] += 1
        await emit(room)
        return
    room['current'] = select_question(room)
    room['question_index'] += 1
    room['total_questions'] += 1
    room['phase'] = 'question'
    room['result'] = None
    room['serial'] += 1
    serial = room['serial']
    room['deadline'] = timestamp() + SECONDS_TO_ANSWER * 1000
    await emit(room)
    asyncio.create_task(expire_question(room, serial))


async def expire_question(room, serial):
    await asyncio.sleep(SECONDS_TO_ANSWER + 0.03)
    if room['phase'] == 'question' and room['serial'] == serial:
        await resolve(room, False)


async def resolve(room, success):
    if room['phase'] != 'question':
        return
    player = room['players'][room['turn_index']]
    player['score'] += SUCCESS_POINTS if success else MISS_POINTS
    room['phase'] = 'reveal'
    room['result'] = {'success': success, 'player': player['name'], 'change': SUCCESS_POINTS if success else MISS_POINTS}
    room['deadline'] = None
    room['serial'] += 1
    serial = room['serial']
    await emit(room)
    asyncio.create_task(advance_later(room, serial))


async def advance_later(room, serial):
    await asyncio.sleep(REVEAL_SECONDS)
    if room['phase'] == 'reveal' and room['serial'] == serial:
        await issue_question(room)


async def end_turn_at(room, turn_serial):
    # One timer per person. The end of a turn is not dependent on a client button.
    await asyncio.sleep(TURN_SECONDS)
    if room['turn_serial'] != turn_serial or room['phase'] not in ('question', 'reveal', 'turn_wait'):
        return
    # A final still-open prompt counts as a miss. No half-answered prompt is kept.
    if room['phase'] == 'question':
        room['players'][room['turn_index']]['score'] += MISS_POINTS
    room['serial'] += 1  # invalidate any pending per-question tasks
    room['turn_index'] += 1
    room['current'] = None
    room['result'] = None
    room['deadline'] = None
    room['turn_deadline'] = None
    room['question_index'] = 0
    if room['turn_index'] >= len(room['players']):
        room['phase'] = 'finished'
        room['next_start_at'] = None
        await emit(room)
    else:
        room['phase'] = 'intermission'
        room['next_start_at'] = timestamp() + round(CHANGEOVER_SECONDS * 1000)
        await emit(room)
        asyncio.create_task(continue_after_changeover(room, turn_serial))


async def continue_after_changeover(room, prev_turn_serial):
    await asyncio.sleep(CHANGEOVER_SECONDS)
    if room['phase'] == 'intermission' and room['turn_serial'] == prev_turn_serial:
        await begin_turn(room)


def create_room(name, identity, ws):
    code = fresh_code()
    person = {'id': identity, 'name': name, 'score': 0, 'ws': ws, 'last_ai': 0}
    ROOMS[code] = {
        'code': code, 'players': [person], 'host': identity,
        'phase': 'lobby', 'queue': [], 'turn_index': 0, 'question_index': 0,
        'total_questions': 0, 'turn_serial': 0,
        'current': None, 'result': None, 'deadline': None, 'turn_deadline': None,
        'next_start_at': None, 'serial': 0,
        'used_bank': set(), 'last_active': time.time()
    }
    return ROOMS[code]


async def generate_ai(genre):
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        return random.sample(BANK.get(genre, [q for arr in BANK.values() for q in arr]), 3), False
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'あなたは日本語の短時間大喜利のお題作家です。誰でも5秒で一言回答できる、短く、面白く、安全な大喜利のお題を3個だけ作ってください。差別・暴力・露骨な性的内容は禁止。JSONオブジェクトのみ出力し、形式は {"questions":["...","...","..."]}。各お題70文字以内。'},
            {'role': 'user', 'content': f'ジャンル: {genre if genre in GENRES else "おまかせ"}。3個作成してください。'},
        ],
        'response_format': {'type': 'json_object'},
        'temperature': 1.0, 'max_tokens': 320
    }
    try:
        timeout = __import__('aiohttp').ClientTimeout(total=12)
        async with ClientSession(timeout=timeout) as client:
            async with client.post('https://api.openai.com/v1/chat/completions',
                    headers={'Authorization': f'Bearer {key}'}, json=payload) as resp:
                if resp.status != 200:
                    raise ValueError(f'API HTTP {resp.status}')
                answer = await resp.json()
        data = json.loads(answer['choices'][0]['message']['content'])
        questions = [clean(x, 80) for x in data.get('questions', []) if clean(x, 80)]
        if len(questions) >= 3:
            return questions[:3], True
    except (Exception,):
        pass
    return random.sample(BANK.get(genre, [q for arr in BANK.values() for q in arr]), 3), False


async def handle_action(ws, data, connection):
    action = data.get('action')
    if action in ('create', 'join'):
        if connection.get('room'):
            await fail(ws, '既にルームに参加しています。')
            return
        name = clean(data.get('name'), 16)
        pid = clean(data.get('identity'), 64)
        if not name or not re.fullmatch(r'[a-zA-Z0-9_-]{16,64}', pid):
            await fail(ws, '名前を入力してもう一度お試しください。')
            return
        if action == 'create':
            room = create_room(name, pid, ws)
        else:
            code = clean(data.get('room'), 6)
            room = ROOMS.get(code)
            if not room:
                await fail(ws, 'そのルームは見つかりません。')
                return
            old = find_player(room, pid)
            if old:
                if old.get('ws') and old['ws'] is not ws:
                    await old['ws'].close()
                old['ws'] = ws
                old['name'] = name
            else:
                if room['phase'] != 'lobby':
                    await fail(ws, 'ゲーム進行中です。参加は次のゲームから可能です。')
                    return
                if len(room['players']) >= MAX_PLAYERS:
                    await fail(ws, 'このルームは満員です。')
                    return
                if any(x['name'] == name for x in room['players']):
                    await fail(ws, 'その名前は既に使われています。')
                    return
                room['players'].append({'id': pid, 'name': name, 'score': 0, 'ws': ws, 'last_ai': 0})
        connection['room'] = room
        connection['identity'] = pid
        await emit(room)
        return

    room = connection.get('room')
    pid = connection.get('identity')
    if not room or not find_player(room, pid) or find_player(room, pid).get('ws') is not ws:
        await fail(ws, 'ルームに参加してください。')
        return
    room['last_active'] = time.time()
    player = find_player(room, pid)
    is_host = room['host'] == pid

    if action == 'submit':
        if room['phase'] == 'finished':
            await fail(ws, 'ゲーム終了後はお題を追加できません。')
            return
        prompt = clean(data.get('text'), 90)
        if len(prompt) < 5:
            await fail(ws, 'お題は5文字以上で入力してください。')
            return
        if sum(1 for p in room['queue'] if p['authorId'] == pid) >= 15 or len(room['queue']) >= 100:
            await fail(ws, '出題待ちがいっぱいです。')
            return
        kind = 'ai-choice' if data.get('kind') == 'ai-choice' else 'user'
        # An AI-choice earns the same points as manual submission.
        room['queue'].append({'text': prompt, 'authorId': pid, 'authorName': player['name'], 'kind': kind})
        await write(ws, {'type': 'submitted', 'message': 'お題を出題待ちに追加しました！'})
        await emit(room)
    elif action == 'suggest':
        if time.time() - player.get('last_ai', 0) < 6:
            await fail(ws, '候補の更新は6秒空けてください。')
            return
        player['last_ai'] = time.time()
        genre = clean(data.get('genre'), 20)
        if genre not in GENRES:
            genre = random.choice(GENRES)
        questions, actually_ai = await generate_ai(genre)
        await write(ws, {'type': 'suggestions', 'questions': questions, 'ai': actually_ai, 'genre': genre})
    elif action == 'start':
        if not is_host or room['phase'] != 'lobby':
            return
        if sum(bool(p.get('ws')) for p in room['players']) < 2:
            await fail(ws, 'オンラインの参加者が2人以上必要です。')
            return
        room['players'] = [p for p in room['players'] if p.get('ws')]
        room['queue'] = [q for q in room['queue'] if find_player(room, q['authorId'])]
        room['turn_index'] = 0
        await begin_turn(room)
    elif action == 'mark':
        if room['phase'] != 'question':
            return
        answerer = room['players'][room['turn_index']]['id']
        success = data.get('success') is True
        if (success and pid in (answerer, room['host'])) or (not success and pid in (answerer, room['host'])):
            if timestamp() >= room['deadline']:
                await resolve(room, False)
            else:
                await resolve(room, success)
    elif action == 'restart':
        if not is_host or room['phase'] != 'finished':
            return
        for p in room['players']:
            p['score'] = 0
        room['serial'] += 1
        room['turn_serial'] += 1
        room.update(phase='lobby', queue=[], turn_index=0, question_index=0,
                    total_questions=0, current=None, result=None, deadline=None,
                    turn_deadline=None, next_start_at=None)
        await emit(room)
    elif action == 'leave':
        connection['leaving'] = True
        await ws.close()
    else:
        await fail(ws, '不明な操作です。')


async def transfer_host_later(room, former_host):
    await asyncio.sleep(7)
    player = find_player(room, former_host)
    if room['host'] == former_host and (not player or not player.get('ws')):
        replacement = next((x for x in room['players'] if x.get('ws')), None)
        if replacement:
            room['host'] = replacement['id']
            await emit(room)


async def websocket(request):
    ws = web.WebSocketResponse(heartbeat=25, max_msg_size=8192)
    await ws.prepare(request)
    connection = {}
    try:
        async for event in ws:
            if event.type == WSMsgType.TEXT:
                try:
                    data = json.loads(event.data)
                    if not isinstance(data, dict):
                        raise ValueError
                    await handle_action(ws, data, connection)
                except (ValueError, TypeError, json.JSONDecodeError):
                    await fail(ws, 'リクエストを確認してください。')
            elif event.type == WSMsgType.ERROR:
                break
    finally:
        room = connection.get('room')
        if room:
            p = find_player(room, connection.get('identity'))
            if p and p.get('ws') is ws:
                p['ws'] = None
                # Keep identities on temporary disconnect so reconnect preserves room and points.
                if connection.get('leaving') and room['phase'] == 'lobby':
                    room['players'] = [x for x in room['players'] if x['id'] != p['id']]
                    room['queue'] = [x for x in room['queue'] if x['authorId'] != p['id']]
                if room['host'] == p['id']:
                    asyncio.create_task(transfer_host_later(room, p['id']))
                await emit(room)
    return ws


async def cleanup(app):
    while True:
        await asyncio.sleep(300)
        now = time.time()
        for code, room in list(ROOMS.items()):
            if not any(p.get('ws') for p in room['players']) and now - room['last_active'] > 1800:
                del ROOMS[code]


async def on_startup(app):
    app['cleanup_task'] = asyncio.create_task(cleanup(app))


async def on_cleanup(app):
    app['cleanup_task'].cancel()
    try:
        await app['cleanup_task']
    except asyncio.CancelledError:
        pass


app = web.Application()
app.router.add_get('/ws', websocket)
app.router.add_get('/health', lambda request: web.json_response({'status': 'ok', 'rooms': len(ROOMS)}))
app.router.add_static('/static/', path=ROOT / 'public', show_index=False)
app.router.add_get('/', lambda request: web.FileResponse(ROOT / 'public' / 'index.html'))
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=PORT)
