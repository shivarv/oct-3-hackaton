import { useEffect, useRef, useState, type ComponentType } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ME_KEY } from "../api";
import type { User, View } from "../types";
import { Avatar } from "./Avatar";
import { HomeIcon, LogOutIcon, SettingsIcon, UserIcon, UsersIcon } from "./Icons";

interface Props {
  me: User;
  view: View;
  onNavigate: (view: View) => void;
}

function AccountMenu({ me, onNavigate }: { me: User; onNavigate: (view: View) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      // Drop everything cached for this member, then show the login page.
      queryClient.removeQueries();
      queryClient.setQueryData(ME_KEY, null);
    },
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const go = (view: View) => {
    setOpen(false);
    onNavigate(view);
  };

  return (
    <div className="account" ref={ref}>
      <button className="account-trigger" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu">
        <Avatar name={me.name} id={me.id} size={32} />
        <span className="account-label">Me ▾</span>
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu-header">
            <Avatar name={me.name} id={me.id} size={52} />
            <div className="person-info">
              <strong>{me.name}</strong>
              <span className="muted xs">@{me.username}</span>
              <span className="muted xs clamp-2">{me.headline}</span>
            </div>
          </div>
          <button className="btn outline block small-btn" onClick={() => go({ page: "profile", userId: me.id })}>
            View profile
          </button>
          <div className="menu-sep" />
          <button role="menuitem" className="menu-item" onClick={() => go({ page: "settings" })}>
            <SettingsIcon size={18} /> Settings & privacy
          </button>
          <button role="menuitem" className="menu-item" onClick={() => logout.mutate()} disabled={logout.isPending}>
            <LogOutIcon size={18} /> {logout.isPending ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}

export function Navbar({ me, view, onNavigate }: Props) {
  const tab = (target: View, label: string, Icon: ComponentType<{ size?: number }>, active: boolean) => (
    <button className={`nav-tab ${active ? "active" : ""}`} onClick={() => onNavigate(target)}>
      <Icon size={22} />
      <span>{label}</span>
    </button>
  );

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <button className="logo" onClick={() => onNavigate({ page: "feed" })} aria-label="Home">
          in
        </button>
        <span className="brand">LinkedOut</span>
        <nav className="nav-tabs">
          {tab({ page: "feed" }, "Home", HomeIcon, view.page === "feed")}
          {tab({ page: "network" }, "Network", UsersIcon, view.page === "network")}
          {tab({ page: "profile", userId: me.id }, "Profile", UserIcon, view.page === "profile" && view.userId === me.id)}
          {tab({ page: "settings" }, "Settings", SettingsIcon, view.page === "settings")}
        </nav>
        <AccountMenu me={me} onNavigate={onNavigate} />
      </div>
    </header>
  );
}
