import { Link, useParams } from "react-router-dom";
import StageCanvas from "./StageCanvas.jsx";
import { api } from "./api";
import { storeKeys, useSWR } from "./store";

export default function ViewerStagePage({ user, onLogout }) {
  const { conversationId } = useParams();
  const { data: conversation } = useSWR(
    conversationId ? storeKeys.conversation(conversationId) : null,
    () => api.getConversation(conversationId)
  );

  const title = conversation?.title || "Stage Viewer";

  return (
    <div className="viewer-page">
      <header className="viewer-header">
        <div className="viewer-header-left">
          <Link to="/" className="viewer-back">
            ← Editor
          </Link>
          <h1 className="viewer-title">{title}</h1>
        </div>
        <div className="viewer-header-right">
          <span className="viewer-filter-pill">Period: Last 12 months</span>
          <span className="viewer-user">{user.email}</span>
          <button type="button" className="link-btn" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="viewer-main">
        <StageCanvas
          conversationId={conversationId}
          readOnly
          variant="orion"
        />
      </main>
    </div>
  );
}
