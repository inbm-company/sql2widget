import { useState } from "react";

export default function MessageDeleteButton({ message, busy, readOnly, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  if (readOnly || !message?.id) return null;
  const isQuestion = message.role === "user";

  async function remove() {
    if (busy || deleting) return;
    setDeleting(true);
    setError("");
    try {
      await onDelete(message);
    } catch (err) {
      setError(err?.message || "메시지를 삭제하지 못했습니다.");
    } finally {
      setDeleting(false);
    }
  }

  return <div className="chat-message-delete">
    <button type="button" className="text-btn chat-turn-delete" disabled={busy || deleting}
      onClick={() => { setConfirming(!confirming); setError(""); }} aria-expanded={confirming}>
      {isQuestion ? "질문 삭제" : "답변 삭제"}
    </button>
    {confirming ? <div className="chat-turn-delete-confirm">
      <p>{isQuestion ? "이 질문만 삭제할까요? 연결된 답변은 남습니다."
        : "이 답변과 답변에 포함된 위젯·처리 내역만 삭제할까요?"}</p>
      <p className="muted">다른 질문·답변과 프로젝트에 저장된 자료는 유지됩니다. 삭제 후 복구할 수 없습니다.</p>
      <button type="button" className="text-btn" disabled={busy || deleting} onClick={remove}>
        {deleting ? "삭제 중…" : "삭제 확인"}
      </button>
      <button type="button" className="text-btn" disabled={deleting} onClick={() => setConfirming(false)}>취소</button>
    </div> : null}
    {error ? <p className="error" role="alert">{error}</p> : null}
  </div>;
}
