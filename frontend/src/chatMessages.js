export function shouldShowPendingMessage(conversation, pendingMessage) {
  if (!pendingMessage || (conversation && conversation.id !== pendingMessage.conversationId)) return false;

  // A focus/reconnect refresh can return the saved question before /api/chat finishes.
  return !(conversation?.messages || []).some((message) =>
    message.role === "user" &&
    message.content === pendingMessage.content &&
    !pendingMessage.existingMessageIds.includes(message.id)
  );
}
