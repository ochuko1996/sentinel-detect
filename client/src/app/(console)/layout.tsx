import { RequireAuth } from "@/components/layout/RequireAuth";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SideNav } from "@/components/layout/SideNav";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <SiteHeader />
      <div className="flex flex-1 overflow-hidden">
        <SideNav />
        <main className="flex-1 overflow-y-auto overflow-x-hidden px-6 py-8 sm:px-10">
          {children}
        </main>
      </div>
    </RequireAuth>
  );
}
