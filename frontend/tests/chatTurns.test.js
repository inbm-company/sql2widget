import test from "node:test";
import assert from "node:assert/strict";
import { conversationTurns, shouldShowPendingMessage } from "../src/chatMessages.js";

const q = (id) => ({ id, role: "user", content: "같은 질문" });
const a = (id, parent) => ({ id, role: "assistant", meta: { reply_to_message_id: parent } });

test("regeneration goes under its original question without merging repeated question text", () => {
  const turns = conversationTurns([q("q1"), a("a1", "q1"), q("q2"), a("a2", "q2"), a("again", "q1")]);
  assert.deepEqual(turns.map((turn) => turn.question.id), ["q1", "q2"]);
  assert.deepEqual(turns.map((turn) => turn.answers.map((message) => message.id)), [["a1", "again"], ["a2"]]);
});

test("legacy answers retain their nearest preceding question", () => {
  const turns = conversationTurns([q("q1"), {id: "legacy", role: "assistant"}, q("q2")]);
  assert.equal(turns[0].answers[0].id, "legacy");
  assert.equal(turns[1].answers.length, 0);
});

test("a missing explicit parent is never silently attached to another question", () => {
  const turns = conversationTurns([q("q1"), a("orphan", "deleted")]);
  assert.equal(turns[0].answers.length, 0);
  assert.equal(turns[1].question, null);
});

test("replaying an existing question never adds a pending user bubble", () => {
  const pending = {id: "send", conversationId: "chat", replyToMessageId: "q1", content: "같은 질문", existingMessageIds: []};
  assert.equal(shouldShowPendingMessage({id: "chat", messages: []}, pending), false);
});


test("deleting a question retains its answers as standalone messages, never reassigned", () => {
  const turns = conversationTurns([q("earlier"), a("retained-answer", "deleted-question")]);
  assert.equal(turns[0].question.id, "earlier");
  assert.equal(turns[0].answers.length, 0);
  assert.equal(turns[1].question, null);
  assert.equal(turns[1].answers[0].id, "retained-answer");
});

test("deleting one answer retains the question and other regenerated answers", () => {
  const turns = conversationTurns([q("q1"), a("kept-answer", "q1")]);
  assert.equal(turns[0].question.id, "q1");
  assert.deepEqual(turns[0].answers.map((message) => message.id), ["kept-answer"]);
});
