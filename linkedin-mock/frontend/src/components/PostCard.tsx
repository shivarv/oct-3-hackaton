import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { Post, User, View } from "../types";
import { Avatar } from "./Avatar";
import { EditIcon, MessageIcon, SendIcon, ThumbsUpIcon, TrashIcon } from "./Icons";
import { timeAgo } from "../time";

interface Props {
  post: Post;
  me: User;
  onNavigate: (v: View) => void;
}

export function PostCard({ post, me, onNavigate }: Props) {
  const queryClient = useQueryClient();
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(post.content);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["posts"] });

  const like = useMutation({ mutationFn: () => api.toggleLike(post.id), onSuccess: refresh });
  const remove = useMutation({ mutationFn: () => api.deletePost(post.id), onSuccess: refresh });
  const save = useMutation({
    mutationFn: () => api.updatePost(post.id, draft),
    onSuccess: () => {
      setEditing(false);
      void refresh();
    },
  });
  const addComment = useMutation({
    mutationFn: () => api.addComment(post.id, comment),
    onSuccess: () => {
      setComment("");
      void refresh();
    },
  });

  const isMine = post.author.id === me.id;
  const liked = post.likes.includes(me.id);
  const goTo = (userId: string) => onNavigate({ page: "profile", userId });

  const startEdit = () => {
    setDraft(post.content);
    save.reset();
    setEditing(true);
  };

  const submitEdit = (e: FormEvent) => {
    e.preventDefault();
    if (draft.trim() && draft.trim() !== post.content) save.mutate();
    else setEditing(false);
  };

  const submitComment = (e: FormEvent) => {
    e.preventDefault();
    if (comment.trim()) addComment.mutate();
  };

  return (
    <article className="card post">
      <header className="post-header">
        <button className="avatar-button" onClick={() => goTo(post.author.id)} aria-label={post.author.name}>
          <Avatar name={post.author.name} id={post.author.id} size={48} />
        </button>
        <div className="post-meta">
          <button className="link name" onClick={() => goTo(post.author.id)}>
            {post.author.name}
            {isMine && <span className="chip">You</span>}
          </button>
          <span className="muted small clamp-1">{post.author.headline}</span>
          <span className="muted xs">
            {timeAgo(post.created_at)}
            {post.edited_at && " · Edited"}
          </span>
        </div>
        {isMine && !editing && (
          <div className="post-tools">
            <button className="icon-btn" onClick={startEdit} title="Edit post" aria-label="Edit post">
              <EditIcon size={18} />
            </button>
            <button
              className="icon-btn danger"
              onClick={() => {
                if (window.confirm("Delete this post?")) remove.mutate();
              }}
              disabled={remove.isPending}
              title="Delete post"
              aria-label="Delete post"
            >
              <TrashIcon size={18} />
            </button>
          </div>
        )}
      </header>

      {editing ? (
        <form className="edit-box" onSubmit={submitEdit}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={3000}
            rows={Math.min(12, Math.max(3, draft.split("\n").length + 1))}
            autoFocus
          />
          {save.isError && <p className="error small">{save.error.message}</p>}
          <div className="form-actions">
            <button type="button" className="btn ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button className="btn primary" disabled={!draft.trim() || save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      ) : (
        <p className="post-content">{post.content}</p>
      )}

      {(post.likes.length > 0 || post.comments.length > 0) && (
        <div className="post-counts muted xs">
          <span className="like-count">
            {post.likes.length > 0 && (
              <>
                <span className="like-bubble">
                  <ThumbsUpIcon size={10} />
                </span>
                {post.likes.length}
              </>
            )}
          </span>
          {post.comments.length > 0 && (
            <button className="link" onClick={() => setShowComments((s) => !s)}>
              {post.comments.length} {post.comments.length === 1 ? "comment" : "comments"}
            </button>
          )}
        </div>
      )}

      <div className="post-actions">
        <button className={`action ${liked ? "liked" : ""}`} onClick={() => like.mutate()} disabled={like.isPending}>
          <ThumbsUpIcon size={18} /> {liked ? "Liked" : "Like"}
        </button>
        <button className="action" onClick={() => setShowComments((s) => !s)}>
          <MessageIcon size={18} /> Comment
        </button>
      </div>

      {showComments && (
        <section className="comments">
          <form className="comment-form" onSubmit={submitComment}>
            <Avatar name={me.name} id={me.id} size={32} />
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a comment…"
              maxLength={1000}
            />
            <button className="icon-btn primary" disabled={!comment.trim() || addComment.isPending} aria-label="Send">
              <SendIcon size={16} />
            </button>
          </form>
          {post.comments.map((c) => (
            <div key={c.id} className="comment">
              <Avatar name={c.author.name} id={c.author.id} size={32} />
              <div className="comment-bubble">
                <div>
                  <button className="link name small" onClick={() => goTo(c.author.id)}>
                    {c.author.name}
                  </button>
                  <span className="muted xs"> · {timeAgo(c.created_at)}</span>
                </div>
                <p>{c.text}</p>
              </div>
            </div>
          ))}
        </section>
      )}
    </article>
  );
}
