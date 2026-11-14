// App shell: sidebar, top bar, command palette, notifications, user menu.
// Canonical copy: frontend/design-system/shell/  (per-app config in app/shell/)
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Component, ElementRef, HostListener, OnDestroy, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterModule } from '@angular/router';
import { Subscription, filter } from 'rxjs';
import { AuthService } from '../../services/auth';
import { AppBarService } from '../../services/app-bar-service';
import { ThemeService } from '../../services/theme';
import { SiteContextService } from '../../shell/site-context';
import { SHELL_CONFIG } from '../../shell/shell-config';
import { ShellDataService } from '../../shell/shell-data';
import { QuickAction, ShellContext, ShellData, ShellNotification, ShellUser } from '../../shell/types';

@Component({
  selector: 'app-main',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './main.html',
  styleUrls: ['./main.css'],
})
export class Main implements OnInit, OnDestroy {
  private auth = inject(AuthService);
  private router = inject(Router);
  private data: ShellData = inject(ShellDataService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  appBar = inject(AppBarService);
  theme = inject(ThemeService);
  site = inject(SiteContextService);
  config = SHELL_CONFIG;

  collapsed = signal(false);
  drawerOpen = signal(false);
  user = signal<ShellUser>({ name: '', subtitle: '' });
  badges = signal<Record<string, number>>({});
  notifications = signal<ShellNotification[]>([]);
  contexts = signal<ShellContext[]>([]);
  menu = signal<'none' | 'user' | 'notes' | 'context'>('none');
  paletteOpen = signal(false);
  query = signal('');
  active = signal(0);
  @ViewChild('paletteInput') paletteInput?: ElementRef<HTMLInputElement>;

  initials = computed(() => (this.user().name || '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase());
  noteCount = computed(() => this.notifications().length);
  results = computed<QuickAction[]>(() => {
    const q = this.query().trim().toLowerCase();
    const nav: QuickAction[] = this.config.sections.flatMap((s) => s.items.map((i) => ({ label: i.label, icon: i.icon, route: i.route, hint: s.title })));
    const all = [...this.config.quickActions.map((a) => ({ ...a, hint: a.hint || 'Action' })), ...nav];
    const hits = q ? all.filter((a) => a.label.toLowerCase().includes(q) || (a.hint || '').toLowerCase().includes(q)) : all;
    const extra = q && this.config.searchAction ? this.config.searchAction(this.query().trim()) : null;
    return extra ? [extra, ...hits] : hits;
  });
  private subs = new Subscription();

  ngOnInit() {
    if (!this.browser) return;
    try { this.collapsed.set(localStorage.getItem('sidebar') === 'collapsed'); } catch {}
    this.refresh();
    this.subs.add(this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => {
      this.drawerOpen.set(false);
      this.menu.set('none');
      this.loadBadges();
    }));
  }

  ngOnDestroy() { this.subs.unsubscribe(); }

  refresh() {
    this.subs.add(this.data.user().subscribe({ next: (u) => this.user.set(u), error: () => {} }));
    this.loadBadges();
    if (this.data.contexts) {
      this.subs.add(this.data.contexts().subscribe({ next: (c) => this.contexts.set(c), error: () => {} }));
    }
  }

  loadBadges() {
    this.subs.add(this.data.badges().subscribe({ next: (b) => this.badges.set(b), error: () => {} }));
    this.subs.add(this.data.notifications().subscribe({ next: (n) => this.notifications.set(n), error: () => {} }));
  }

  get contextLabel() { return this.data.contextLabel || 'Context'; }

  toggleCollapse() {
    this.collapsed.update((v) => !v);
    try { localStorage.setItem('sidebar', this.collapsed() ? 'collapsed' : 'open'); } catch {}
  }

  toggleMenu(m: 'user' | 'notes' | 'context', ev: Event) {
    ev.stopPropagation();
    this.menu.set(this.menu() === m ? 'none' : m);
  }

  chooseContext(c: ShellContext) {
    this.site.select(c.id, c.label);
    this.menu.set('none');
  }

  openPalette() {
    this.query.set('');
    this.active.set(0);
    this.paletteOpen.set(true);
    setTimeout(() => this.paletteInput?.nativeElement.focus());
  }

  go(a: QuickAction | ShellNotification) {
    this.paletteOpen.set(false);
    this.menu.set('none');
    this.router.navigateByUrl(a.route);
  }

  paletteKey(ev: KeyboardEvent) {
    const n = this.results().length;
    if (ev.key === 'ArrowDown') { ev.preventDefault(); this.active.set((this.active() + 1) % Math.max(n, 1)); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); this.active.set((this.active() - 1 + n) % Math.max(n, 1)); }
    else if (ev.key === 'Enter' && n) { ev.preventDefault(); this.go(this.results()[this.active()]); }
    else if (ev.key === 'Escape') { this.paletteOpen.set(false); }
  }

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent) {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); this.openPalette(); }
    if (ev.key === 'Escape') { this.menu.set('none'); this.drawerOpen.set(false); }
  }

  @HostListener('document:click')
  closeMenus() { this.menu.set('none'); }

  logOut() {
    this.auth.logout().subscribe({
      next: () => this.router.navigate(['/login']),
      error: () => this.router.navigate(['/login']),
    });
  }
}
