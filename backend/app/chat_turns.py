"""Question/reply relationships for legacy and regenerated chat messages."""

from fastapi import HTTPException


def message_turns(messages):
    turns, by_id, current = [], {}, None
    for message in messages or []:
        if message.get("role") == "user":
            current = {"question": message, "answers": []}
            turns.append(current)
            if message.get("id"):
                by_id[message["id"]] = current
        elif message.get("role") == "assistant":
            parent = (message.get("meta") or {}).get("reply_to_message_id")
            target = by_id.get(parent) if parent else current
            if target:
                target["answers"].append(message)
            else:
                turns.append({"question": None, "answers": [message]})
    return turns


def active_answers(answers):
    """Keep the latest regenerated answer and its subsequent continuation chain."""
    result = []
    for answer in answers:
        if (answer.get("meta") or {}).get("response_mode") == "continue":
            result.append(answer)
        else:
            result = [answer]
    return result


def context_messages(messages):
    """Use the latest answer per question; old alternatives remain in the UI only."""
    result = []
    for turn in message_turns(messages):
        if turn["question"]:
            result.append(turn["question"])
        if turn["answers"]:
            result.extend(active_answers(turn["answers"]))
    return result


def prepare_response(body, conversation):
    messages = conversation.get("messages") or []
    if bool(body.reply_to_message_id) != bool(body.response_mode):
        raise HTTPException(400, "기존 질문 ID와 응답 동작을 함께 지정해 주세요.")
    if not body.reply_to_message_id:
        return None, body.message, context_messages(messages), body.route, None
    turns = message_turns(messages)
    index = next((i for i, turn in enumerate(turns)
                  if (turn["question"] or {}).get("id") == body.reply_to_message_id), None)
    if index is None:
        raise HTTPException(404, "이 대화에서 원래 질문을 찾을 수 없습니다.")
    turn = turns[index]
    source = turn["question"]
    before = []
    for earlier in turns[:index]:
        if earlier["question"]:
            before.append(earlier["question"])
        if earlier["answers"]:
            before.extend(active_answers(earlier["answers"]))
    requested_route = (source.get("meta") or {}).get("requested_route")
    if requested_route is None and turn["answers"]:
        last_meta = turn["answers"][-1].get("meta") or {}
        if last_meta.get("route_source") == "user_choice":
            requested_route = last_meta.get("route")
    message = source["content"]
    if body.response_mode == "continue" and turn["answers"]:
        before = before + [source] + active_answers(turn["answers"])
        message = ("원래 요청을 이어서 처리해 주세요. 아래 대화에 이미 완료된 답변과 위젯은 반복하지 말고 "
                   "남아 있는 부분을 처리해 주세요.\n원래 요청: " + source["content"])
    return source, message, before, requested_route, turn
