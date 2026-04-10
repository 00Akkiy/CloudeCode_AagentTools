const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const DB_PATH = path.join(__dirname, 'data', 'db.json');

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function readDB() {
  const raw = fs.readFileSync(DB_PATH, 'utf-8');
  return JSON.parse(raw);
}

function writeDB(data) {
  fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

// クラス一覧取得
app.get('/api/classes', (req, res) => {
  const db = readDB();
  const classes = db.classes.map(c => {
    const booked = db.reservations.filter(r => r.classId === c.id).length;
    return { ...c, booked, available: c.capacity - booked };
  });
  res.json(classes);
});

// クラス詳細取得
app.get('/api/classes/:id', (req, res) => {
  const db = readDB();
  const cls = db.classes.find(c => c.id === parseInt(req.params.id));
  if (!cls) return res.status(404).json({ error: 'クラスが見つかりません' });
  const booked = db.reservations.filter(r => r.classId === cls.id).length;
  res.json({ ...cls, booked, available: cls.capacity - booked });
});

// 予約作成
app.post('/api/reservations', (req, res) => {
  const { classId, name, phone, email } = req.body;

  if (!classId || !name || !phone || !email) {
    return res.status(400).json({ error: '全ての項目を入力してください' });
  }

  const emailReg = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailReg.test(email)) {
    return res.status(400).json({ error: 'メールアドレスの形式が正しくありません' });
  }

  const db = readDB();
  const cls = db.classes.find(c => c.id === parseInt(classId));
  if (!cls) return res.status(404).json({ error: 'クラスが見つかりません' });

  const booked = db.reservations.filter(r => r.classId === cls.id).length;
  if (booked >= cls.capacity) {
    return res.status(409).json({ error: 'このクラスは満席です' });
  }

  const duplicate = db.reservations.find(
    r => r.classId === parseInt(classId) && r.email === email
  );
  if (duplicate) {
    return res.status(409).json({ error: 'このメールアドレスは既に予約済みです' });
  }

  const reservation = {
    id: Date.now(),
    classId: parseInt(classId),
    name,
    phone,
    email,
    createdAt: new Date().toISOString()
  };

  db.reservations.push(reservation);
  writeDB(db);

  res.status(201).json({ message: '予約が完了しました', reservation });
});

// 予約一覧取得（メールで検索）
app.get('/api/reservations', (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: 'メールアドレスを指定してください' });

  const db = readDB();
  const myReservations = db.reservations
    .filter(r => r.email === email)
    .map(r => {
      const cls = db.classes.find(c => c.id === r.classId);
      return { ...r, class: cls };
    });

  res.json(myReservations);
});

// 予約キャンセル
app.delete('/api/reservations/:id', (req, res) => {
  const { email } = req.body;
  const db = readDB();
  const idx = db.reservations.findIndex(
    r => r.id === parseInt(req.params.id) && r.email === email
  );

  if (idx === -1) {
    return res.status(404).json({ error: '予約が見つかりません' });
  }

  db.reservations.splice(idx, 1);
  writeDB(db);
  res.json({ message: '予約をキャンセルしました' });
});

app.listen(PORT, () => {
  console.log(`公民館スクール予約アプリ起動中: http://localhost:${PORT}`);
});
