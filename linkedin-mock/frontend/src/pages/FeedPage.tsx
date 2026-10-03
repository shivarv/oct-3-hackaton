import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { User, View } from "../types";
import { Composer } from "../components/Composer";
import { PostCard } from "../components/PostCard";
import { ProfileCard } from "../components/ProfileCard";
import { Suggestions } from "../components/Suggestions";

interface Props {
  me: User;
  users: User[];
  onNavigate: (v: View) => void;
}

export function FeedPage({ me, users, onNavigate }: Props) {
  const posts = useQuery({ queryKey: ["posts", "feed"], queryFn: () => api.posts() });

  return (
    <div className="layout three-col">
      <ProfileCard user={me} onNavigate={onNavigate} />
      <main className="feed">
        <Composer me={me} />
        {posts.isPending && <p className="muted center">Loading feed…</p>}
        {posts.isError && <p className="error center">{posts.error.message}</p>}
        {posts.data?.length === 0 && <p className="muted center">No posts yet. Be the first!</p>}
        {posts.data?.map((p) => <PostCard key={p.id} post={p} me={me} onNavigate={onNavigate} />)}
      </main>
      <Suggestions me={me} users={users} onNavigate={onNavigate} />
    </div>
  );
}
