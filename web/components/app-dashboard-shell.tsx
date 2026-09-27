import Link from "next/link";
import type { ReactNode } from "react";

import { NavUser } from "@/components/nav-user";
import { SidebarProvider } from "@/components/ui/sidebar";
import "@/components/watermelon/agndex-dashboard/dashboard.css";

type DashboardShellProps = {
  active: "overview" | "documents" | "playground" | "llm" | "api" | "settings" | "members" | "billing";
  children: ReactNode;
  organizationName: string;
  user: {
    id: string;
    name: string;
    email: string;
    image?: string | null;
  };
  role: string;
};

const groups = [
  {
    label: "PROJECT",
    items: [
      ["⌂", "Overview", "/dashboard", "overview"],
      ["▤", "Documents", "/dashboard/document", "documents"],
      ["◉", "Playground", "/dashboard/playground", "playground"],
      ["◇", "Knowledge", "/knowledge", ""],
      ["⌁", "Analytics", "/analytics", ""],
    ],
  },
  {
    label: "DEPLOY",
    items: [
      ["⌘", "API Keys", "/api-keys", ""],
      ["</>", "API", "/dashboard/api", "api"],
      ["▣", "Chat Widget", "/chat-widget", ""],
    ],
  },
  {
    label: "CONFIGURE",
    items: [["⚙", "AI & Retrieval", "/dashboard/llm", "llm"]],
  },
  {
    label: "ORGANIZATION",
    items: [
      ["♙", "Members", "/dashboard/settings#members", "members"],
      ["$", "Billing", "/billing", "billing"],
    ],
  },
  {
    label: "SUPPORT",
    items: [["□", "Documentation", "/docs", ""]],
  },
] as const;

function initials(name: string, email: string) {
  const source = name.trim() || email;
  return source
    .split(/\s+|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function AppDashboardShell({ active, children, organizationName, user, role }: DashboardShellProps) {
  const userInitials = initials(user.name, user.email);

  return (
    <SidebarProvider open className="agndex-dashboard flex h-svh overflow-hidden bg-sidebar text-sidebar-foreground">
      <aside className="hidden w-[17.25rem] shrink-0 flex-col px-4 py-5 md:flex bg-sidebar">
        <div className="space-y-2">
          <button className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium hover:bg-sidebar-accent">
            <span className="truncate">{organizationName}</span>
            <span className="text-sidebar-foreground/50">▾</span>
          </button>
        </div>

        <nav className="mt-8 flex flex-1 flex-col gap-7 overflow-y-auto no-scrollbar">
          {groups.map((group) => (
            <div key={group.label}>
              <p className="mb-2 px-3 text-xsm font-medium text-sidebar-muted">{group.label}</p>
              <div className="space-y-1.5">
                {group.items.map(([icon, label, href, key]) => (
                  <Link
                    key={label}
                    href={href}
                    aria-current={key === active ? "page" : undefined}
                    className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-smd tracking-tight text-sidebar-muted-foreground opacity-80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground aria-[current=page]:bg-sidebar-accent aria-[current=page]:font-medium aria-[current=page]:text-sidebar-accent-foreground aria-[current=page]:opacity-100"
                  >
                    <span className="w-5 text-center text-sm">{icon}</span>
                    <span>{label}</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-sidebar-border pt-4">
          <NavUser
            user={{
              id: user.id,
              name: user.name,
              email: user.email,
              avatar: user.image,
              initials: userInitials,
            }}
          />
          <p className="px-3 pt-1 text-xs text-sidebar-muted-foreground">{role}</p>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto md:bg-sidebar md:p-2">
        <div className="min-h-full overflow-hidden bg-background md:rounded-xl">
          <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/50 bg-background/90 px-4 backdrop-blur md:h-16 md:px-6">
            <nav className="text-sm text-muted-foreground">
              <span>Recall</span>
              <span className="mx-2 text-border">|</span>
              <span>{organizationName}</span>
            </nav>
          </header>
          {children}
        </div>
      </main>
    </SidebarProvider>
  );
}
