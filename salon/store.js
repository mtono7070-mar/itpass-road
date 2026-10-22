// 予約データの保存先。claude.ai の公開ページでは共有データベース（db）、
// それ以外（普通のブラウザで開いたとき）はこの端末の localStorage を使う。
window.YukiStore = window.YukiStore || (() => {
  const LS = "yuki-store-v1";
  const subs = new Set();
  let bookings = [], blocks = [], db = null, mode = "local", loaded = true;
  const emit = () => subs.forEach(f => { try { f(); } catch (e) { console.error(e); } });
  function readLocal(){
    try { const d = JSON.parse(localStorage.getItem(LS)) || {}; bookings = d.bookings || []; blocks = d.blocks || []; }
    catch { bookings = []; blocks = []; }
  }
  function writeLocal(){ try { localStorage.setItem(LS, JSON.stringify({bookings, blocks})); } catch {} }
  readLocal();
  addEventListener("storage", e => { if (e.key === LS && mode === "local"){ readLocal(); emit(); } });

  const ready = (async () => {
    try { db = window.claude && window.claude.use ? await window.claude.use("db") : null; } catch { db = null; }
    if (!db) return;
    mode = "db"; loaded = false; bookings = []; blocks = []; emit();
    const fail = e => console.warn("db:", e && e.code, e && e.message);
    db.collection("bookings").onSnapshot(s => { bookings = s.docs.map(d => ({...d.data(), id:d.id})); loaded = true; emit(); }, fail);
    db.collection("blocks").onSnapshot(s => { blocks = s.docs.map(d => ({...d.data(), id:d.id})); emit(); }, fail);
  })();

  return {
    get bookings(){ return bookings; },
    get blocks(){ return blocks; },
    get mode(){ return mode; },
    get loaded(){ return loaded; },
    ready,
    onChange(f){ subs.add(f); },
    async addBooking(b){
      if (mode === "db") return db.collection("bookings").doc(b.no).set(b);
      bookings = bookings.concat([{...b, id:b.no}]); writeLocal(); emit();
    },
    async updateBooking(no, patch){
      if (mode === "db") return db.collection("bookings").doc(no).update(patch);
      bookings = bookings.map(b => b.no === no ? {...b, ...patch} : b); writeLocal(); emit();
    },
    async addBlock(b){
      const id = "blk-" + Date.now().toString(36);
      if (mode === "db") return db.collection("blocks").doc(id).set(b);
      blocks = blocks.concat([{...b, id}]); writeLocal(); emit();
    },
    async removeBlock(id){
      if (mode === "db") return db.collection("blocks").doc(id).delete();
      blocks = blocks.filter(b => b.id !== id); writeLocal(); emit();
    },
  };
})();
