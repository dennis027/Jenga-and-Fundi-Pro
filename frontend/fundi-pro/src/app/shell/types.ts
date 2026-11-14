// Shell contracts. Canonical copy: frontend/design-system/shell/types.ts
import { Observable } from 'rxjs';

export interface NavItem { label: string; icon: string; route: string; exact?: boolean; badge?: string; }
export interface NavSection { title: string; items: NavItem[]; }
export interface QuickAction { label: string; icon: string; route: string; hint?: string; }
export interface ShellConfig {
  brand: string;
  brandIcon: string;
  tagline: string;
  sections: NavSection[];
  quickActions: QuickAction[];
  /** Extra command-palette entry built from the typed text (e.g. "Find worker ..."). */
  searchAction?: (q: string) => QuickAction | null;
}
export interface ShellUser { name: string; subtitle: string; picture?: string | null; }
export interface ShellNotification { icon: string; tone: 'info' | 'ok' | 'warn' | 'danger'; title: string; sub: string; route: string; }
export interface ShellContext { id: number | null; label: string; }

/** Implemented per app in app/shell/shell-data.ts */
export interface ShellData {
  user(): Observable<ShellUser>;
  badges(): Observable<Record<string, number>>;
  notifications(): Observable<ShellNotification[]>;
  /** Optional context switcher (e.g. contractor sites). */
  contexts?(): Observable<ShellContext[]>;
  contextLabel?: string;
}
