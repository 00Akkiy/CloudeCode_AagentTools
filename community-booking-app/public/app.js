// ビュー切り替え
const navBtns = document.querySelectorAll('.nav-btn');
const views = document.querySelectorAll('.view');

navBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    navBtns.forEach(b => b.classList.remove('active'));
    views.forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('view-' + btn.dataset.view).classList.add('active');
  });
});

// トースト通知
function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast' + (isError ? ' error' : '');
  setTimeout(() => toast.classList.add('hidden'), 3000);
}

// クラス一覧取得・表示
async function loadClasses() {
  const container = document.getElementById('class-list');
  container.innerHTML = '<p class="loading">読み込み中...</p>';
  try {
    const res = await fetch('/api/classes');
    const classes = await res.json();
    renderClasses(classes);
  } catch {
    container.innerHTML = '<p class="empty-msg">データの取得に失敗しました</p>';
  }
}

function renderClasses(classes) {
  const container = document.getElementById('class-list');
  if (classes.length === 0) {
    container.innerHTML = '<p class="empty-msg">現在開講中のクラスはありません</p>';
    return;
  }

  container.innerHTML = classes.map(c => {
    const avail = c.available;
    const availClass = avail === 0 ? 'full' : avail <= 3 ? 'low' : 'ok';
    const availText = avail === 0 ? '満席' : `残り ${avail} 席`;
    return `
      <div class="class-card">
        <h3>${c.name}</h3>
        <div class="class-meta">
          <span>講師：${c.instructor}</span>
          <span>日程：${c.schedule}</span>
          <span>場所：${c.room}</span>
          <span>定員：${c.capacity}名</span>
        </div>
        <p class="class-desc">${c.description}</p>
        <div class="class-footer">
          <span class="fee">¥${c.fee.toLocaleString()} / 回</span>
          <span class="availability ${availClass}">${availText}</span>
        </div>
        <button class="btn-book" data-id="${c.id}" data-name="${c.name}" ${avail === 0 ? 'disabled' : ''}>
          ${avail === 0 ? '満席' : '予約する'}
        </button>
      </div>`;
  }).join('');

  document.querySelectorAll('.btn-book:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => openModal(btn.dataset.id, btn.dataset.name));
  });
}

// モーダル
let selectedClassId = null;

async function openModal(classId, className) {
  selectedClassId = classId;
  const res = await fetch('/api/classes/' + classId);
  const cls = await res.json();

  document.getElementById('modal-title').textContent = cls.name + ' の予約';
  document.getElementById('modal-class-info').innerHTML = `
    <strong>講師：</strong>${cls.instructor}<br>
    <strong>日程：</strong>${cls.schedule}<br>
    <strong>場所：</strong>${cls.room}<br>
    <strong>受講料：</strong>¥${cls.fee.toLocaleString()} / 回<br>
    <strong>残席：</strong>${cls.available} 席
  `;

  document.getElementById('form-name').value = '';
  document.getElementById('form-phone').value = '';
  document.getElementById('form-email').value = '';
  document.getElementById('form-error').classList.add('hidden');
  document.getElementById('modal-overlay').classList.remove('hidden');
}

document.getElementById('modal-close').addEventListener('click', () => {
  document.getElementById('modal-overlay').classList.add('hidden');
});
document.getElementById('modal-overlay').addEventListener('click', (e) => {
  if (e.target === document.getElementById('modal-overlay')) {
    document.getElementById('modal-overlay').classList.add('hidden');
  }
});

// 予約フォーム送信
document.getElementById('booking-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('form-name').value.trim();
  const phone = document.getElementById('form-phone').value.trim();
  const email = document.getElementById('form-email').value.trim();
  const errEl = document.getElementById('form-error');
  const submitBtn = document.getElementById('submit-btn');

  errEl.classList.add('hidden');
  submitBtn.disabled = true;
  submitBtn.textContent = '予約中...';

  try {
    const res = await fetch('/api/reservations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ classId: selectedClassId, name, phone, email })
    });
    const data = await res.json();

    if (!res.ok) {
      errEl.textContent = data.error;
      errEl.classList.remove('hidden');
    } else {
      document.getElementById('modal-overlay').classList.add('hidden');
      showToast('予約が完了しました！');
      loadClasses();
    }
  } catch {
    errEl.textContent = '予約に失敗しました。もう一度お試しください。';
    errEl.classList.remove('hidden');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = '予約する';
  }
});

// 予約確認・検索
document.getElementById('search-btn').addEventListener('click', searchReservations);
document.getElementById('search-email').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchReservations();
});

async function searchReservations() {
  const email = document.getElementById('search-email').value.trim();
  const container = document.getElementById('my-reservations-list');
  if (!email) {
    container.innerHTML = '<p class="empty-msg">メールアドレスを入力してください</p>';
    return;
  }

  container.innerHTML = '<p class="loading">検索中...</p>';
  try {
    const res = await fetch('/api/reservations?email=' + encodeURIComponent(email));
    const data = await res.json();
    if (!res.ok) {
      container.innerHTML = '<p class="empty-msg">エラーが発生しました</p>';
      return;
    }
    renderReservations(data, email);
  } catch {
    container.innerHTML = '<p class="empty-msg">データの取得に失敗しました</p>';
  }
}

function renderReservations(reservations, email) {
  const container = document.getElementById('my-reservations-list');
  if (reservations.length === 0) {
    container.innerHTML = '<p class="empty-msg">予約が見つかりませんでした</p>';
    return;
  }

  container.innerHTML = reservations.map(r => {
    const date = new Date(r.createdAt).toLocaleString('ja-JP');
    return `
      <div class="reservation-card" id="res-${r.id}">
        <div class="reservation-info">
          <h4>${r.class ? r.class.name : 'クラス不明'}</h4>
          <p>${r.class ? r.class.schedule : ''} / ${r.class ? r.class.room : ''}</p>
          <p>${r.name} 様</p>
          <p class="reservation-date">予約日時：${date}</p>
        </div>
        <button class="btn-cancel" data-id="${r.id}" data-email="${email}">キャンセル</button>
      </div>`;
  }).join('');

  document.querySelectorAll('.btn-cancel').forEach(btn => {
    btn.addEventListener('click', () => cancelReservation(btn.dataset.id, btn.dataset.email));
  });
}

async function cancelReservation(id, email) {
  if (!confirm('この予約をキャンセルしますか？')) return;

  try {
    const res = await fetch('/api/reservations/' + id, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();

    if (!res.ok) {
      showToast(data.error, true);
    } else {
      document.getElementById('res-' + id)?.remove();
      showToast('予約をキャンセルしました');
      loadClasses();
      const container = document.getElementById('my-reservations-list');
      if (!container.querySelector('.reservation-card')) {
        container.innerHTML = '<p class="empty-msg">予約が見つかりませんでした</p>';
      }
    }
  } catch {
    showToast('キャンセルに失敗しました', true);
  }
}

// 初期ロード
loadClasses();
