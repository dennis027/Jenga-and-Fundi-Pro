import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { duration } from '../../shell/ui';

const API = environment.apiUrl + 'api/';

export const scoreLevel = (s: number) =>
  s >= 85 ? { name: 'Platinum', next: null } : s >= 60 ? { name: 'Gold', next: 85 } : s >= 30 ? { name: 'Silver', next: 60 } : { name: 'Bronze', next: 30 };

@Component({
  selector: 'app-fundi-dash',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './fundi-dash.html',
  styleUrl: './fundi-dash.css',
})
export class FundiDash implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  duration = duration;

  loading = signal(true);
  me = signal<any>(null);
  stats = signal<any>(null);
  gigs = signal<any[]>([]);
  history = signal<any[]>([]);
  completing = signal<number | null>(null);
  today = new Date();
  greeting = (() => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; })();

  score = computed(() => this.me()?.credit_score ?? 0);
  level = computed(() => scoreLevel(this.score()));
  ready = computed(() => this.gigs().filter((g) => g.is_verified));
  waiting = computed(() => this.gigs().filter((g) => !g.is_verified));
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
    }).subscribe((r: any) => {
      this.me.set(r.me); this.stats.set(r.stats); this.gigs.set(r.gigs);
      this.history.set([...r.history].sort((a: any, b: any) => b.start_date.localeCompare(a.start_date)));
      this.loading.set(false);
    });
  }

  complete(g: any) {
    this.completing.set(g.id);
    this.http.post<any>(API + `gigs/${g.id}/complete/`, {}).subscribe({
      next: (res) => {
        this.completing.set(null);
        this.me.update((m) => m && { ...m, credit_score: res.new_score });
        this.snack.open(`Gig completed. Your score is now ${res.new_score}.`, 'OK', { duration: 3500, panelClass: 'success-snackbar' });
        this.load();
      },
      error: (e) => { this.completing.set(null); this.snack.open(e?.error?.error || 'Could not complete this gig.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
