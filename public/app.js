'use strict';
const $ = (id) => document.getElementById(id);
const nickname = $('nickname');
const codeInput = $('join-code');
const landing = $('landing');
const game = $('game');
let ws = null;
let state = null;
let activeCode = null;
let retryTimer = null;
let toastTimer = null;
let clockOffset = 0;
let suggested = [];
let connecting = false;
const identity = getIdentity();

function getIdentity() {
  let token = sessionStorage.getItem('flash_ogiri_player');
  if (!token) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    token = Array.from(bytes, (n) => n.toString(16).padStart(2, '0')).join('');
    sessionStorage.setItem('flash_ogiri_player', token);
  }
  return token;
}
function escapeHTML(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function send(action, payload = {}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) { toast('サーバーとの接続が切れています'); return false; }
  ws.send(JSON.stringify({ action, ...payload }));
  return true;
}
function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3100);
}
function connected(isOnline) {
  $('connection-dot').classList.toggle('online', isOnline);
  $('connection-label').textContent = isOnline ? 'オンライン' : '再接続しています';
}
function connect(initialAction, roomCode) {
  if (connecting) return;
  connecting = true;
  if (ws) { ws.onclose = null; ws.close(); }
  clearTimeout(retryTimer);
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);
  ws.onopen = () => {
    connecting = false;
    connected(true);
    if (initialAction === 'create') send('create', { name: nickname.value.trim(), identity });
    else if (initialAction === 'join') send('join', { name: nickname.value.trim(), identity, room: roomCode });
    else if (activeCode) send('join', { name: nickname.value.trim(), identity, room: activeCode });
  };
  ws.onmessage = ({data}) => {
    let message;
    try { message = JSON.parse(data); } catch { return; }
    if (message.type === 'state') {
      state = message;
      activeCode = state.room;
      clockOffset = message.serverNow - Date.now();
      showGame();
      render();
    } else if (message.type === 'error') {
      toast(message.message);
      $('landing-error').textContent = message.message;
    } else if (message.type === 'submitted') {
      $('question-text').value = '';
      toast(message.message);
    } else if (message.type === 'suggestions') {
      suggested = message.questions;
      renderSuggestions(message.ai);
      $('suggest-btn').disabled = false;
      $('suggest-btn').textContent = '3つ提案 ✦';
    }
  };
  ws.onclose = () => {
    connecting = false;
    connected(false);
    if (activeCode) retryTimer = setTimeout(() => connect('rejoin'), 2200);
  };
  ws.onerror = () => { connecting = false; };
}
function showGame() {
  landing.classList.add('hidden');
  game.classList.remove('hidden');
  $('room-code').textContent = state.room;
  const url = new URL(location.href);
  url.searchParams.set('room', state.room);
  history.replaceState({}, '', url);
}
function nameOf(id) { return state?.players.find(p => p.id === id)?.name || 'プレイヤー'; }
function playerRow(p, i, active = false) {
  const isAnswerer = p.id === state.answererId && state.phase !== 'finished' && state.phase !== 'lobby';
  return `<div class="score-row ${active ? 'active' : ''}"><span class="rank">${i + 1}</span><span class="avatar">${escapeHTML(p.name[0] || '?')}</span><span class="score-name">${escapeHTML(p.name)}${p.id === state.you ? ' <span class="status-bubble">あなた</span>':''}${isAnswerer ? ' <span class="status-bubble">回答者</span>':''}${!p.online ? ' <span class="status-bubble">離席</span>':''}</span><span class="score-value">${p.score}</span></div>`;
}
function rankedPlayers() { return [...state.players].sort((a,b) => b.score - a.score); }
function stageShell(label, tag, center, footer = '') {
  return `<div class="stage-top"><span class="status-label">${label}</span><span class="tag">${tag}</span></div><div class="stage-center spotlight">${center}</div>${footer}`;
}
function render() {
  if (!state) return;
  $('room-code').textContent = state.room;
  $('score-list').innerHTML = rankedPlayers().map((p,i) => playerRow(p,i,p.id===state.answererId)).join('');
  $('player-count').textContent = `${state.players.length} PLAYERS`;
  $('queue-count').textContent = state.queueCount;
  $('question-panel').classList.toggle('hidden', state.phase === 'finished');
  let html = '';
  const answerer = escapeHTML(nameOf(state.answererId));
  const isAnswerer = state.you === state.answererId;
  if (state.phase === 'lobby') {
    html = stageShell('WAITING ROOM', `${state.players.length} / 16 PEOPLE`, `
      <div class="eyebrow">THE GAME STARTS HERE</div><h2>全員集まったら<br>ゲームスタート。</h2>
      <p>回答者は1人60秒！ 各お題は5秒で即答。<br>60秒経ったら自動交代して、全員1周で勝負！</p>
      <p class="hint">ルームコード <strong style="color:var(--cyan)">${state.room}</strong> を友達に共有してください。</p>
      ${state.isHost ? `<div class="stage-actions"><button class="btn btn-primary" data-action="start" ${state.players.length<2?'disabled':''}>60秒チャレンジを開始 ↗</button></div>` : '<p class="hint">ホストが開始するまでお待ちください。</p>'}`);
  } else if (state.phase === 'intermission') {
    html = stageShell('NEXT CHALLENGER', `TURN ${state.turnIndex+1} / ${state.players.length}`, `
      <div class="eyebrow">NEXT UP</div><h2><span class="answerer-name">${answerer}</span> の番！</h2>
      <p>まもなく60秒チャレンジが自動スタートします。</p>
      <div class="changeover-time"><span id="changeover-number">3</span><small>秒後に開始</small></div>
      <p class="hint">出題待ち ${state.queueCount} 問 ／ お題は不足しても自動補充</p>`);
  } else if (state.phase === 'question') {
    html = `<div class="stage-top"><span class="status-label">NOW ANSWERING</span><span class="q-counter">TURN ${state.turnIndex+1} / ${state.players.length}　·　第${state.questionIndex}問</span></div>
      <div class="turn-timer">${answerer} の残り時間 <strong id="turn-number">60.0</strong><span>秒</span><div class="turn-track"><div id="turn-progress"></div></div></div>
      <div class="stage-center"><span class="overline">${answerer} へのお題</span><h2 class="big-question">${escapeHTML(state.current?.text || '')}</h2>
      <div class="countdown-box"><div id="timer-number" class="timer-number">5.00</div><div class="progress-track"><div id="progress-fill" class="progress-fill"></div></div><span class="hint">秒以内に回答！</span></div>
      <div class="stage-actions">${isAnswerer ? '<button class="btn btn-primary" data-action="success">回答した！ +10点</button><button class="btn btn-outline" data-action="miss">パス −5点</button>' : ''}
      ${state.isHost && !isAnswerer ? '<button class="btn btn-primary" data-action="success">回答成功にする</button><button class="btn btn-danger" data-action="miss">時間切れにする</button>':''}</div></div>`;
  } else if (state.phase === 'reveal') {
    const success = state.result?.success;
    html = stageShell('RESULT', `TURN ${state.turnIndex+1} / ${state.players.length}`, `
      <div class="turn-timer">${answerer} の残り時間 <strong id="turn-number">60.0</strong><span>秒</span><div class="turn-track"><div id="turn-progress"></div></div></div>
      <div class="result-sign ${success?'yes':'no'}">${success?'CLEAR!':'TIME UP!'}</div>
      <h2 class="result-points" style="color:${success?'var(--cyan)':'var(--red)'}">${success?'+10':'−5'} PT</h2>
      <p>${answerer} ${success?'は時間内に回答！':'は時間切れ！'}</p><p class="hint">${escapeHTML(state.current?.text || '')}</p>
      <p class="hint">次のお題に進みます...</p>`);
  } else if (state.phase === 'turn_wait') {
    html = stageShell('LAST SECONDS', `TURN ${state.turnIndex+1} / ${state.players.length}`, `
      <div class="turn-timer">${answerer} の残り時間 <strong id="turn-number">0.0</strong><span>秒</span><div class="turn-track"><div id="turn-progress"></div></div></div>
      <h2>残り時間わずか！</h2><p>次のお題を5秒間表示できないため、交代まで待機します。</p>`);
  } else if (state.phase === 'finished') {
    const sorted = rankedPlayers();
    html = stageShell('GAME FINISHED', 'FINAL RESULTS', `
      <div class="eyebrow">ONE FULL ROTATION COMPLETE</div>
      <h2>結果発表！</h2><p>全員が1度ずつ回答者を担当しました。</p>
      <div class="score-table">${sorted.map((p,i)=>playerRow(p,i,i===0)).join('')}</div>
      <p class="hint">合計 ${state.totalQuestions} 問・${state.players.length} 人参加</p>
      ${state.isHost?'<div class="stage-actions"><button class="btn btn-primary" data-action="restart">もう1ゲーム ↻</button></div>':''}`);
  }
  $('stage').innerHTML = html;
  updateClock();
}
function updateClock() {
  if (!state) return;
  const now = Date.now() + clockOffset;
  if (state.turnDeadline) {
    const turnRemaining = Math.max(0, state.turnDeadline - now);
    const n = $('turn-number');
    const b = $('turn-progress');
    if (n) { n.textContent = (turnRemaining / 1000).toFixed(1); n.classList.toggle('danger', turnRemaining <= 10000); }
    if (b) b.style.width = (turnRemaining / (state.turnSeconds * 1000) * 100) + '%';
  }
  if (state.phase === 'intermission' && state.nextStartAt) {
    const n = $('changeover-number');
    if (n) n.textContent = Math.ceil(Math.max(0, state.nextStartAt - now) / 1000);
  }
  if (state.phase === 'question' && state.deadline) {
    const remaining = Math.max(0, state.deadline - now);
    const n = $('timer-number');
    const b = $('progress-fill');
    if (!n || !b) return;
    n.textContent = (remaining / 1000).toFixed(2);
    n.classList.toggle('danger', remaining <= 1500);
    b.classList.toggle('danger', remaining <= 1500);
    b.style.width = (remaining / (state.answerSeconds * 1000) * 100) + '%';
  }
}
function renderSuggestions(isAI) {
  const list = $('suggestions');
  list.innerHTML = `<div class="suggestion-note">${isAI?'AIが作成した':'内蔵のお題から選んだ'}候補です。タップすると投稿できます。</div>`+
      suggested.map((q,i) => `<button class="suggestion" data-suggestion="${i}"><span>${escapeHTML(q)}</span><strong>選ぶ ＋</strong></button>`).join('');
}
function attemptJoin(action) {
  $('landing-error').textContent = '';
  const name = nickname.value.trim();
  if (!name) { $('landing-error').textContent = 'プレイヤー名を入力してください。'; nickname.focus(); return; }
  if (action === 'join' && !/^\d{6}$/.test(codeInput.value.trim())) {
    $('landing-error').textContent = '6桁のルームコードを入力してください。'; codeInput.focus(); return;
  }
  localStorage.setItem('flash_ogiri_nickname', name);
  connect(action, codeInput.value.trim());
}
$('create-btn').addEventListener('click', () => attemptJoin('create'));
$('join-btn').addEventListener('click', () => attemptJoin('join'));
codeInput.addEventListener('keydown', (ev) => {if(ev.key === 'Enter')attemptJoin('join');});
$('copy-room').addEventListener('click', async () => {
  const url = new URL(location.href); url.searchParams.set('room', activeCode);
  try { await navigator.clipboard.writeText(url.toString()); toast('招待リンクをコピーしました！'); }
  catch { toast(`ルームコード：${activeCode}`); }
});
$('leave-btn').addEventListener('click', () => {
  if (ws) {send('leave'); ws.onclose = null; ws.close();}
  activeCode = null; state = null; suggested = [];
  const url = new URL(location.href); url.searchParams.delete('room'); history.replaceState({}, '', url);
  game.classList.add('hidden'); landing.classList.remove('hidden');
  connected(false);
});
$('stage').addEventListener('click', (ev) => {
  const button = ev.target.closest('button[data-action]'); if (!button) return;
  const action = button.dataset.action;
  if (action === 'success') send('mark', { success:true });
  else if (action === 'miss') send('mark', { success:false });
  else send(action);
});
$('submit-question').addEventListener('click', () => {
  const prompt = $('question-text').value.trim();
  if (prompt.length < 5) {toast('お題は5文字以上で入力してください。');return;}
  send('submit', {text:prompt, kind:'user'});
});
$('suggest-btn').addEventListener('click', () => {
  if (send('suggest', {genre:$('genre').value})) {
    $('suggest-btn').disabled=true; $('suggest-btn').textContent='提案中...';
    setTimeout(()=> { $('suggest-btn').disabled=false; $('suggest-btn').textContent='3つ提案 ✦'; }, 14000);
  }
});
$('suggestions').addEventListener('click', (ev) => {
  const btn = ev.target.closest('button[data-suggestion]'); if (!btn) return;
  const prompt = suggested[Number(btn.dataset.suggestion)];
  if (prompt && send('submit', {text:prompt,kind:'ai-choice'})) {
    btn.disabled=true; btn.querySelector('strong').textContent='投稿済み';
  }
});
document.addEventListener('keydown', (ev) => {
  const field = document.activeElement?.tagName;
  if (ev.code === 'Space' && !ev.repeat && state?.phase === 'question' && state.you === state.answererId
      && !['INPUT','TEXTAREA','SELECT','BUTTON'].includes(field)) {
    ev.preventDefault();
    send('mark', { success:true });
  }
});
setInterval(updateClock,40);
nickname.value=localStorage.getItem('flash_ogiri_nickname')||'';
const initialCode=new URLSearchParams(location.search).get('room');
if(initialCode && /^\d{6}$/.test(initialCode)) codeInput.value=initialCode;
// Connect on Create/Join to avoid racing the first click.
