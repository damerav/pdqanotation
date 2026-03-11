import { useState, useEffect } from "react";
import { Amplify } from "aws-amplify";
import { Authenticator } from "@aws-amplify/ui-react";
import { fetchAuthSession } from "aws-amplify/auth";
import "@aws-amplify/ui-react/styles.css";
import awsConfig from "./utils/aws-config";
import UploadPage from "./pages/UploadPage";
import HistoryPage from "./pages/HistoryPage";
import AdminPage from "./pages/AdminPage";
import "./App.css";

Amplify.configure(awsConfig);

export default function App() {
  return (
    <Authenticator loginMechanisms={["username"]} variation="modal">
      {({ signOut, user }) => <Shell user={user} signOut={signOut} />}
    </Authenticator>
  );
}

function Shell({ user, signOut }) {
  const [page, setPage] = useState("upload");
  const [isAdmin, setIsAdmin] = useState(false);
  const email = user?.signInDetails?.loginId ?? "";

  useEffect(() => {
    async function checkAdmin() {
      try {
        const session = await fetchAuthSession();
        const groups = session.tokens?.idToken?.payload?.["cognito:groups"] || [];
        setIsAdmin(groups.includes("admin"));
      } catch {
        setIsAdmin(false);
      }
    }
    checkAdmin();
  }, [user]);

  return (
    <div className="app-shell">
      <nav className="topnav">
        <span className="brand">Email Annotator</span>
        <div className="nav-links">
          <button className={`nav-btn ${page === "upload" ? "active" : ""}`} onClick={() => setPage("upload")}>
            New Job
          </button>
          <button className={`nav-btn ${page === "history" ? "active" : ""}`} onClick={() => setPage("history")}>
            History
          </button>
          {isAdmin && (
            <button className={`nav-btn ${page === "admin" ? "active" : ""}`} onClick={() => setPage("admin")}>
              Admin
            </button>
          )}
        </div>
        <div className="nav-user">
          {isAdmin && <span className="role-badge">Admin Role</span>}
          <span className="user-email">{email}</span>
          <button className="signout-btn" onClick={signOut}>Sign Out</button>
        </div>
      </nav>

      <main className="main-content">
        {page === "upload" && <UploadPage userEmail={email} />}
        {page === "history" && <HistoryPage userEmail={email} />}
        {page === "admin" && isAdmin && <AdminPage />}
      </main>
    </div>
  );
}
