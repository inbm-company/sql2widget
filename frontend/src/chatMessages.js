export function shouldShowPendingMessage(conversation, pendingMessage) {
  if (!pendingMessage || pendingMessage.replyToMessageId || (conversation && conversation.id !== pendingMessage.conversationId)) return false;

  // Prefer exact send IDs; retain content matching for older callers.
  return !(conversation?.messages || []).some((message) => {
    if (message.role !== "user") return false;
    if (pendingMessage.id) return message.meta?.client_message_id === pendingMessage.id;
    return message.content === pendingMessage.content && !pendingMessage.existingMessageIds.includes(message.id);
  });
}

export function conversationTurns(messages = []) {
  const turns = [];
  const byId = new Map();
  let current = null;
  for (const message of messages) {
    if (message.role === "user") {
      current = { question: message, answers: [] };
      turns.push(current);
      byId.set(message.id, current);
    } else if (message.role === "assistant") {
      const parent = message.meta?.reply_to_message_id;
      const target = parent ? byId.get(parent) : current;
      if (target) target.answers.push(message);
      else turns.push({ question: null, answers: [message] });
    }
  }
  return turns;
}
