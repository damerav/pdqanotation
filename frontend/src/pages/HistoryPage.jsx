import { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import { get } from "aws-amplify/api";

export default function HistoryPage({ userEmail }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => { loadHistory(); }, []);

  async function loadHistory() {
    setLoading(true);
    setError(null);
    try {
      const session = await fetchAuthSession();
      const token = session.tokens.idToken.toString();
      const response = await get({
        apiName: "EmailAnnotatorAPI",
        path: "/jobs",
        options: { headers: { Authorization: token } },
      }).response;
      const data = await response.body.json();
      setJobs(data.jobs || []);
    } catch (err) {
      setError("Could not load job history. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h2>Job History</h2>
          <p className="subtitle" style={{ marginBottom: 0 }}>
            All annotation jobs for {userEmail}
          </p>
        </div>
        <button onClick={loadHistory} style={{
          background: "transparent", border: "1px solid #d1d5db",
          borderRadius: "7px", padding: "0.4rem 0.9rem",
          cursor: "pointer", fontSize: "0.85rem", color: "#374151"
        }}>
          ↻ Refresh
        </button>
      </div>

      {loading && <p className="empty-state">Loading…</p>}
      {error && <p className="empty-state" style={{ color: "#991b1b" }}>{error}</p>}
      {!loading && !error && jobs.length === 0 && (
        <p className="empty-state">No jobs yet. Upload your first email to get started.</p>
      )}

      {!loading && jobs.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {jobs.map((job) => <JobCard key={job.job_id} job={job} />)}
        </div>
      )}
    </div>
  );
}

function JobCard({ job }) {
  const score = job.review_score;
  const counts = job.issue_counts || {};
  const scoreColor = score == null ? "#6b7280"
    : score >= 80 ? "#166534"
    : score >= 60 ? "#92400e"
    : "#991b1b";
  const scoreBg = score == null ? "#f9fafb"
    : score >= 80 ? "#f0fdf4"
    : score >= 60 ? "#fffbeb"
    : "#fef2f2";

  return (
    <div style={{
      border: "1px solid #e5e7eb", borderRadius: "10px",
      padding: "1rem 1.25rem", background: "white"
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: "1rem" }}>

        {/* Score circle */}
        <div style={{
          minWidth: "52px", height: "52px", borderRadius: "50%",
          background: scoreBg, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          border: `1px solid ${scoreColor}22`
        }}>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: scoreColor, lineHeight: 1 }}>
            {score ?? "—"}
          </span>
          <span style={{ fontSize: "0.55rem", color: "#9ca3af" }}>/100</span>
        </div>

        {/* Job details */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.2rem" }}>
            <span style={{ fontWeight: 600, fontSize: "0.9rem", fontFamily: "monospace" }}>
              {job.filename}
            </span>
            <span className={`badge ${job.status}`}>{job.status}</span>
          </div>

          {job.subject_line && (
            <p style={{ fontSize: "0.82rem", color: "#374151", margin: "0 0 0.3rem",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {job.subject_line}
            </p>
          )}

          {job.review_summary && (
            <p style={{ fontSize: "0.78rem", color: "#6b7280", margin: "0 0 0.4rem",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {job.review_summary}
            </p>
          )}

          <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.75rem", flexWrap: "wrap" }}>
            {(counts.critical > 0) && (
              <span style={{ color: "#991b1b", fontWeight: 600 }}>
                ● {counts.critical} critical
              </span>
            )}
            {(counts.warning > 0) && (
              <span style={{ color: "#92400e", fontWeight: 600 }}>
                ● {counts.warning} warnings
              </span>
            )}
            {(counts.info > 0) && (
              <span style={{ color: "#1d4ed8" }}>
                ● {counts.info} info
              </span>
            )}
            <span style={{ color: "#9ca3af", marginLeft: "auto" }}>
              {new Date(job.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Download */}
        {job.pdf_url && (
          <a href={job.pdf_url} target="_blank" rel="noreferrer"
            className="download-link"
            style={{ whiteSpace: "nowrap", alignSelf: "center" }}>
            ↓ PDF
          </a>
        )}
      </div>
    </div>
  );
}
