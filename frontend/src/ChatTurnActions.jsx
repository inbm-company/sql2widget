export default function ChatTurnActions({ question, answers, interrupted, busy, readOnly, allowContinue = true, onRegenerate, onContinue }) {
  if (readOnly || !question?.id) return null;
  const last = answers.at(-1);
  const incomplete = interrupted || question.meta?.response_pending || !last
    || ["budget", "no_progress", "incomplete"].includes(last.meta?.loop_stop);
  return <div className="chat-turn-action-row">
    {allowContinue && incomplete && !busy ? <button type="button" className="text-btn"
      onClick={() => onContinue(question)}>계속하기</button> : null}
    {last && !busy ? <button type="button" className="text-btn"
      onClick={() => onRegenerate(question)}>다시 생성</button> : null}
  </div>;
}
