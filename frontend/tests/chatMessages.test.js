import { test } from "node:test";
import assert from "node:assert/strict";
import { shouldShowPendingMessage } from "../src/chatMessages.js";

const question = { id: "old-question", role: "user", content: "매출을 보여줘" };
const pending = { conversationId: "chat-1", content: question.content, existingMessageIds: [question.id] };

test("a repeated question keeps its placeholder until the new user message arrives", () => {
  const conversation = { id: "chat-1", messages: [question] };
  assert.equal(shouldShowPendingMessage(conversation, pending), true);
  const refreshed = { ...conversation, messages: [...conversation.messages, { ...question, id: "new-question" }] };
  assert.equal(shouldShowPendingMessage(refreshed, pending), false);
  assert.equal(conversation.messages.length, 1);
  assert.equal(refreshed.messages.length, 2);
});

test("a saved question hides the placeholder both before and after the answer arrives", () => {
  const messages = [question, { ...question, id: "new-question" }];
  assert.equal(shouldShowPendingMessage({ id: "chat-1", messages }, pending), false);
  assert.equal(shouldShowPendingMessage({ id: "chat-1", messages: [...messages,
    { id: "answer", role: "assistant", content: "매출 결과" },
  ] }, pending), false);
});

test("unrelated user messages and assistant text do not hide the pending question", () => {
  assert.equal(shouldShowPendingMessage({ id: "chat-1", messages: [question,
    { id: "other", role: "user", content: "다른 질문" },
    { id: "answer", role: "assistant", content: question.content },
  ] }, pending), true);
});

test("pending questions are scoped to their conversation and cleared on completion", () => {
  assert.equal(shouldShowPendingMessage({ id: "chat-2", messages: [] }, pending), false);
  assert.equal(shouldShowPendingMessage(undefined, pending), true);
  assert.equal(shouldShowPendingMessage({ id: "chat-1" }, pending), true);
  assert.equal(shouldShowPendingMessage({ id: "chat-1" }, null), false);
});
