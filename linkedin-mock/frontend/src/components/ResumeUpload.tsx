import { useRef, useState, type DragEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { User } from "../types";
import { DownloadIcon, EyeIcon, FileIcon, TrashIcon, UploadIcon } from "./Icons";

const MAX_BYTES = 5 * 1024 * 1024;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ResumeUpload({ me }: { me: User }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const onDone = () => queryClient.invalidateQueries({ queryKey: ["users"] });
  const upload = useMutation({ mutationFn: (file: File) => api.uploadResume(file), onSuccess: onDone });
  const remove = useMutation({ mutationFn: () => api.deleteResume(), onSuccess: onDone });

  const pick = (file: File | undefined) => {
    setLocalError(null);
    upload.reset();
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setLocalError("Please choose a PDF file.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setLocalError("PDF must be 5 MB or smaller.");
      return;
    }
    upload.mutate(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  };

  const error = localError ?? (upload.isError ? upload.error.message : null) ?? (remove.isError ? remove.error.message : null);

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={(e) => {
          pick(e.target.files?.[0]);
          e.target.value = ""; // allow re-selecting the same file
        }}
      />

      {me.resume ? (
        <div className="file-tile">
          <div className="file-icon">
            <FileIcon size={26} />
            <span>PDF</span>
          </div>
          <div className="file-info">
            <strong className="clamp-1">{me.resume.filename}</strong>
            <span className="muted xs">
              {formatBytes(me.resume.size)} · uploaded {new Date(me.resume.uploaded_at).toLocaleDateString()}
            </span>
          </div>
          <div className="file-actions">
            <a className="icon-btn" href={api.resumeUrl(me.id)} target="_blank" rel="noopener noreferrer" title="View">
              <EyeIcon size={18} />
            </a>
            <a className="icon-btn" href={api.resumeUrl(me.id, true)} title="Download">
              <DownloadIcon size={18} />
            </a>
            <button
              type="button"
              className="icon-btn"
              onClick={() => inputRef.current?.click()}
              disabled={upload.isPending}
              title="Replace"
            >
              <UploadIcon size={18} />
            </button>
            <button
              type="button"
              className="icon-btn danger"
              onClick={() => {
                if (window.confirm("Remove your resume?")) remove.mutate();
              }}
              disabled={remove.isPending}
              title="Remove"
            >
              <TrashIcon size={18} />
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          disabled={upload.isPending}
        >
          <span className="dropzone-icon">
            <UploadIcon size={26} />
          </span>
          <strong>{upload.isPending ? "Uploading…" : "Drag & drop your resume here"}</strong>
          <span className="muted small">
            or <span className="accent">browse files</span> · PDF up to 5 MB
          </span>
        </button>
      )}

      {upload.isPending && me.resume && <p className="muted small">Uploading…</p>}
      {error && <p className="error small">{error}</p>}
    </div>
  );
}
