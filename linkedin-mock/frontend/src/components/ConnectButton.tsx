import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { User } from "../types";
import { CheckIcon, PlusIcon } from "./Icons";

export function ConnectButton({ me, target }: { me: User; target: User }) {
  const queryClient = useQueryClient();
  const connected = me.connections.includes(target.id);
  const toggle = useMutation({
    mutationFn: () => (connected ? api.disconnect(target.id) : api.connect(target.id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  if (me.id === target.id) return null;
  return (
    <button
      className={`btn ${connected ? "secondary" : "outline"}`}
      onClick={() => toggle.mutate()}
      disabled={toggle.isPending}
      title={connected ? "Click to remove connection" : undefined}
    >
      {connected ? <CheckIcon size={16} /> : <PlusIcon size={16} />}
      {connected ? "Connected" : "Connect"}
    </button>
  );
}
