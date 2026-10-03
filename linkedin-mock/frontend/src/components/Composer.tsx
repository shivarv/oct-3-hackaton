import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { User } from "../types";
import { Avatar } from "./Avatar";
import { SendIcon } from "./Icons";

const MAX = 3000;

export function Composer({ me }: { me: User }) {
  const [content, setContent] = useState("");
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: () => api.createPost(content),
    onSuccess: () => {
      setContent("");
      void queryClient.invalidateQueries({ queryKey: ["posts"] });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (content.trim()) create.mutate();
  };

  return (
    <form className="card composer" onSubmit={submit}>
      <div className="composer-row">
        <Avatar name={me.name} id={me.id} size={48} />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={`What's on your mind, ${me.name.split(" ")[0]}?`}
          maxLength={MAX}
          rows={content ? 4 : 2}
        />
      </div>
      {create.isError && <p className="error small">{create.error.message}</p>}
      <div className="composer-actions">
        <span className="muted small">{content ? `${content.length}/${MAX}` : ""}</span>
        <button className="btn primary" disabled={!content.trim() || create.isPending}>
          <SendIcon size={16} />
          {create.isPending ? "Posting…" : "Post"}
        </button>
      </div>
    </form>
  );
}
