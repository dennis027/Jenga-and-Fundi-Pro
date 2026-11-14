import { I18nService, TPipe } from '../../services/i18n';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';

const API = environment.apiUrl + 'api/';

export const scoreLevel = (s: number) =>
  s >= 85 ? { name: 'Platinum', next: null } : s >= 60 ? { name: 'Gold', next: 85 } : s >= 30 ? { name: 'Silver', next: 60 } : { name: 'Bronze', next: 30 };

@Component({
  selector: 'app-fundi-dash',
  standalone: true,
  imports: [TPipe, CommonModule, RouterModule],
  templateUrl: './fundi-dash.html',
  styleUrl: './fundi-dash.css',
})
export class FundiDash implements OnInit {
  private i18n = inject(I18nService);
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  duration = (v: number, u: string) => this.i18n.t(u === 'weeks' ? (v === 1 ? '{0} week' : '{0} weeks') : (v === 1 ? '{0} day' : '{0} days'), v);

  loading = signal(true);
  me = signal<any>(null);
  stats = signal<any>(null);
  gigs = signal<any[]>([]);
  history = signal<any[]>([]);
  completing = signal<number | null>(null);
  checkedIn = signal<Record<number, string>>({});
  checking = signal<number | null>(null);
  apps = signal<any[]>([]);
  today = new Date();
  greeting = (() => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; })();

  score = computed(() => this.me()?.credit_score ?? 0);
  level = computed(() => scoreLevel(this.score()));
  ready = computed(() => this.gigs().filter((g) => g.is_verified));
  waiting = computed(() => this.gigs().filter((g) => !g.is_verified));
  accepted = computed(() => this.apps().filter((a) => a.status === 'accepted'));
  steps = computed(() => {
    const m = this.me() || {};
    return [
      { done: !!(m.full_name && m.national_id && m.phone && m.county), label: 'Complete your profile', hint: 'Name, ID number, phone and area', route: '/main-menu/profile' },
      { done: !!m.id_verified, label: 'Verify your ID', hint: '+20 to your score', route: '/main-menu/verification-status' },
      { done: this.gigs().length + this.history().length > 0, label: 'Log your first gig', hint: 'At the site where you work', route: '/main-menu/gigs' },
      { done: this.history().length > 0, label: 'Complete a verified gig', hint: 'It goes on your certificate', route: '/main-menu/gig-summary' },
    ];
  });
  stepsDone = computed(() => this.steps().filter((s) => s.done).length);
  firstName = computed(() => ((this.me()?.full_name || this.me()?.username || '') as string).split(' ')[0]);

  ngOnInit() {
    this.appBar.setTitle('Dashboard');
    this.appBar.clearActions();
    if (this.browser) this.load();
  }

  load() {
    const safe = <T>(o: any, f: T) => o.pipe(catchError(() => of(f)));
    forkJoin({
      me: safe(this.http.get<any>(API + 'user/'), null),
      stats: safe(this.http.get<any>(API + 'fundi/dashboard/stats/'), null),
      gigs: safe(this.http.get<any[]>(API + 'user-gigs/'), []),
      history: safe(this.http.get<any[]>(API + 'user-work-history/'), []),
      checkins: safe(this.http.get<number[]>(API + 'my-check-ins/today/'), []),
      apps: safe(this.http.get<any[]>(API + 'my-applications/'), []),
    }).subscribe((r: any) => {
      this.me.set(r.me); this.stats.set(r.stats); this.gigs.set(r.gigs); this.apps.set(r.apps);
      this.checkedIn.set(Object.fromEntries((r.checkins as number[]).map((id) => [id, 'today'])));
      this.history.set([...r.history].sort((a: any, b: any) => b.start_date.localeCompare(a.start_date)));
      this.loading.set(false);
    });
  }

  checkIn(g: any) {
    this.checking.set(g.id);
    this.http.post<any>(API + `gigs/${g.id}/check-in/`, {}).subscribe({
      next: (r) => { this.checking.set(null); this.checkedIn.update((m) => ({ ...m, [g.id]: r.checked_in_at }));
        this.snack.open(this.i18n.t('Checked in at {0}.', g.organization_name), this.i18n.t('OK'), { duration: 3000, panelClass: 'success-snackbar' }); },
      error: (e) => { this.checking.set(null); this.snack.open(e?.error?.detail || this.i18n.t('Could not check in.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  checkedTime(id: number) { const v = this.checkedIn()[id]; return v && v !== 'today' ? v : null; }

  complete(g: any) {
    this.completing.set(g.id);
    this.http.post<any>(API + `gigs/${g.id}/complete/`, {}).subscribe({
      next: (res) => {
        this.completing.set(null);
        this.me.update((m) => m && { ...m, credit_score: res.new_score });
        this.snack.open(this.i18n.t('Gig completed. Your score is now {0}.', res.new_score), this.i18n.t('OK'), { duration: 3500, panelClass: 'success-snackbar' });
        this.load();
      },
      error: (e) => { this.completing.set(null); this.snack.open(e?.error?.error || this.i18n.t('Could not complete this gig.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
