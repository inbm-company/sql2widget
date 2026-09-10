import { Link, useParams } from "react-router-dom";
import StageCanvas from "./StageCanvas.jsx";

export default function ViewerStagePage({ user, onLogout }) {
  const { projectId } = useParams();

  return (
    <div className="viewer-page">
      <header className="viewer-header">
        <div className="viewer-header-left">
          <Link to="/" className="viewer-back">
            ← Editor
          </Link>
          <h1 className="viewer-title">Project Stage</h1>
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
          projectId={projectId}
          readOnly
          variant="orion"
        />
      </main>
    </div>
  );
}
