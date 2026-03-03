import { useState, useRef } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import { post } from "aws-amplify/api";
import awsConfig from "../utils/aws-config";

const API_BASE = awsConfig.API.REST.EmailAnnotatorAPI.endpoint;

export default function UploadPage({ userEmail }) {
  const [file, setFile] = useState(null);
  const [imagesZip, setImagesZip] = useState(null);
  const [subject, setSubject] = useState("");
  const [preheader, setPreheader] = useState("");
  const [recipientEmail, setRecipientEmail] = useState(userEmail);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [imagesDragOver, setImagesDragOver] = useState(false);
  const inputRef = useRef();
  const imagesInputRef = useRef();

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".html")) setFile(dropped);
  }

  function handleImagesDrop(e) {
    e.preventDefault();
    setImagesDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".zip")) setImagesZip(dropped);
  }

  function handleImagesChange(e) {
    const selected = e.target.files[0];
    if (selected?.name.endsWith(".zip")) setImagesZip(selected);
  }

  function handleRemoveImages() {
    setImagesZip(null);
    if (imagesInputRef.current) imagesInputRef.current.value = "";
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) return;
    setStatus("processing");
    setResult(null);
    setError("");

    try {
      const session = await fetchAuthSession();
      const token = session.tokens.idToken.toString();
      const htmlContent = await file.text();

      let imagesS3Key = "";
      let jobId = "";

      // If images ZIP provided, get pre-signed URL and upload to S3
      if (imagesZip) {
        setStatus("uploading-images");

        const uploadUrlResp = await fetch(`${API_BASE}/upload-url`, {
          method: "POST",
          headers: {
            Authorization: token,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });

        if (!uploadUrlResp.ok) {
          throw new Error("Failed to get upload URL for images.");
        }

        const uploadUrlData = await uploadUrlResp.json();
        imagesS3Key = uploadUrlData.images_s3_key;
        jobId = uploadUrlData.job_id;

        // Upload ZIP directly to S3 via pre-signed URL
        const putResp = await fetch(uploadUrlData.upload_url, {
          method: "PUT",
          headers: { "Content-Type": "application/zip" },
          body: imagesZip,
        });

        if (!putResp.ok) {
          throw new Error("Failed to upload images ZIP to S3.");
        }

        setStatus("processing");
      }

      // Build request body — include images key and job_id if images were uploaded
      const requestBody = {
        filename: file.name,
        html_content: htmlContent,
        subject_line: subject,
        preheader_text: preheader,
        recipient_email: recipientEmail || userEmail,
      };
      if (imagesS3Key) requestBody.images_s3_key = imagesS3Key;
      if (jobId) requestBody.job_id = jobId;

      const response = await post({
        apiName: "EmailAnnotatorAPI",
        path: "/process",
        options: {
          headers: { Authorization: token },
          body: requestBody,
        },
      }).response;

      const data = await response.body.json();

      if (data.job_id) {
        setStatus("success");
        setResult(data);
        setFile(null);
        setImagesZip(null);
        setSubject("");
        setPreheader("");
      } else {
        throw new Error(data.error || "Unexpected server response.");
      }
    } catch (err) {
      setStatus("error");
      setError(err.message);
    }
  }

  return (
    <div>
      <div className="card">
        <h2>New Annotation Job</h2>
        <p className="subtitle">
          Upload your HTML email. We'll review it with AI, generate annotated screenshots,
          and deliver the PDF to your inbox in about 60 seconds.
        </p>

        <form onSubmit={handleSubmit}>
          {/* HTML file upload zone */}
          <div
            className={`upload-zone ${dragOver ? "drag-over" : ""}`}
            onClick={() => inputRef.current.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input ref={inputRef} type="file" accept=".html"
              onChange={(e) => setFile(e.target.files[0])} />
            <div className="upload-icon">📧</div>
            <p>Drag and drop your HTML email file here, or click to browse</p>
            <p className="file-hint">Accepts .html files only</p>
          </div>

          {file && (
            <div className="selected-file">
              ✅ <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
            </div>
          )}

          {/* Images ZIP upload zone (optional) */}
          <div
            className={`upload-zone ${imagesDragOver ? "drag-over" : ""}`}
            style={{
              marginTop: "1rem",
              borderStyle: "dashed",
              background: imagesZip ? "#f0fdf4" : "#fafafa",
            }}
            onClick={() => imagesInputRef.current.click()}
            onDragOver={(e) => { e.preventDefault(); setImagesDragOver(true); }}
            onDragLeave={() => setImagesDragOver(false)}
            onDrop={handleImagesDrop}
          >
            <input ref={imagesInputRef} type="file" accept=".zip"
              onChange={handleImagesChange} />
            <div className="upload-icon">🖼️</div>
            <p>Drag and drop an images ZIP file here, or click to browse</p>
            <p className="file-hint">Optional — .zip containing images referenced in your HTML</p>
          </div>

          {imagesZip && (
            <div className="selected-file" style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span>
                🖼️ <strong>{imagesZip.name}</strong> ({(imagesZip.size / 1024).toFixed(1)} KB)
              </span>
              <button
                type="button"
                onClick={handleRemoveImages}
                style={{
                  background: "none", border: "none", color: "#991b1b",
                  cursor: "pointer", fontSize: "0.85rem", fontWeight: 600,
                }}
              >
                Remove
              </button>
            </div>
          )}

          <div style={{ marginTop: "1.5rem" }}>
            <div className="field">
              <label>Subject Line <span style={{ color: "#9ca3af" }}>(optional)</span></label>
              <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g. Bayer Kerendia Pharmacy — PDQ-PEM-25-075" />
            </div>
            <div className="field">
              <label>Preheader Text <span style={{ color: "#9ca3af" }}>(optional)</span></label>
              <input type="text" value={preheader} onChange={(e) => setPreheader(e.target.value)}
                placeholder="e.g. NEW! KERENDIA Blister Packs Now Available" />
            </div>
            <div className="field">
              <label>Deliver PDF to Email</label>
              <input type="email" value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)} required />
            </div>
          </div>

          <button type="submit" className="btn-primary"
            disabled={!file || status === "processing" || status === "uploading-images"}>
            {status === "uploading-images"
              ? "Uploading images…"
              : status === "processing"
                ? "Processing…"
                : "Generate Annotated PDF"}
          </button>
        </form>

        {status === "uploading-images" && (
          <div className="status-banner processing">
            <span>📤</span>
            Uploading images ZIP to S3…
          </div>
        )}

        {status === "processing" && (
          <div className="status-banner processing">
            <span>⏳</span>
            Uploading and reviewing your email — this takes about 30–60 seconds…
          </div>
        )}

        {status === "error" && (
          <div className="status-banner error">
            <span>❌</span> {error}
          </div>
        )}

        {status === "success" && result && (
          <ReviewResult result={result} recipientEmail={recipientEmail || userEmail} />
        )}
      </div>

      <div className="card" style={{ background: "#fafafa", border: "1px solid #e5e7eb" }}>
        <h2 style={{ fontSize: "0.95rem", color: "#6b7280", marginBottom: "0.75rem" }}>
          What AWS Bedrock reviews
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", fontSize: "0.85rem" }}>
          {[
            ["🔗 Links", "Broken URLs, missing UTM params, placeholder hrefs"],
            ["♿ Accessibility", "Missing alt text, non-descriptive link text, lang attribute"],
            ["⚖️ Compliance", "CAN-SPAM unsubscribe, physical address, pharma disclosures"],
            ["✍️ Content", "Placeholder text, spam trigger words, weak CTAs"],
            ["📬 Deliverability", "Image-to-text ratio, spam keywords, HTML size"],
            ["🔧 Technical", "Unsupported CSS, missing viewport meta, inline styles"],
          ].map(([title, desc]) => (
            <div key={title} style={{
              background: "white", border: "1px solid #e5e7eb",
              borderRadius: "8px", padding: "0.75rem"
            }}>
              <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{title}</div>
              <div style={{ color: "#6b7280", fontSize: "0.8rem" }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ReviewResult({ result, recipientEmail }) {
  const score = result.review_score;
  const counts = result.issue_counts || {};
  const summary = result.review_summary || "";

  const scoreColor = score >= 80 ? "#166534" : score >= 60 ? "#92400e" : "#991b1b";
  const scoreBg = score >= 80 ? "#f0fdf4" : score >= 60 ? "#fffbeb" : "#fef2f2";
  const scoreBorder = score >= 80 ? "#bbf7d0" : score >= 60 ? "#fde68a" : "#fecaca";

  return (
    <div style={{ marginTop: "1.25rem" }}>
      <div style={{
        background: scoreBg, border: `1px solid ${scoreBorder}`,
        borderRadius: "10px", padding: "1.25rem", marginBottom: "0.75rem"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
          <div style={{ textAlign: "center", minWidth: "70px" }}>
            <div style={{ fontSize: "2.2rem", fontWeight: 700, color: scoreColor, lineHeight: 1 }}>
              {score ?? "—"}
            </div>
            <div style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "2px" }}>/ 100</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, marginBottom: "0.3rem", fontSize: "0.95rem" }}>
              Review Complete
            </div>
            <p style={{ fontSize: "0.85rem", color: "#374151", margin: "0 0 0.5rem" }}>{summary}</p>
            <div style={{ display: "flex", gap: "1rem", fontSize: "0.8rem" }}>
              <span style={{ color: "#991b1b", fontWeight: 600 }}>
                {counts.critical || 0} critical
              </span>
              <span style={{ color: "#92400e", fontWeight: 600 }}>
                {counts.warning || 0} warnings
              </span>
              <span style={{ color: "#1d4ed8", fontWeight: 600 }}>
                {counts.info || 0} info
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="status-banner success">
        ✅ Annotated PDF with full review report sent to <strong>{recipientEmail}</strong>
      </div>
    </div>
  );
}
