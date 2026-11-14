import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute, Router } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { duration, initials } from '../../shell/ui';

const API = environment.apiUrl + 'api/';

interface Known { username: string; name: string; gigs: number; sites: Set<string>; last: string; }
interface Profile {
  id: number; username: string; full_name: string; phone: string; county: string; constituency: string; ward: string;
  is_verified: boolean; id_verified: boolean; credit_score: number; gigs: any[];
  completed_gigs: number; rating_avg: number | null; ratings_count: number;
  skills: string[]; years_experience: number | null; day_rate: number | null; bio: string; is_available: boolean;
  available_from: string | null; in_crew: boolean;
}
type DirTab = 'known' | 'crew' | 'find';

@Component({
  selector: 'app-manage-workers',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './manage-workers.html',
  styleUrl: './manage-workers.css',
})
export class ManageWorkers implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  private snack = inject(MatSnackBar);
  initials = initials; duration = duration;
  emptySet = new Set<string>();

  q = signal('');
  filter = signal('');
  known = signal<Known[]>([]);
  loading = signal(true);
  searching = signal(false);
  profile = signal<Profile | null>(null);
  notFound = signal(false);
  dirTab = signal<DirTab>('known');
  crew = signal<any[]>([]);
  found = signal<any[] | null>(null);
  trade = signal('');
  county = signal('');
  onlyAvailable = signal(true);
  finding = signal(false);
  openPosts = signal<any[]>([]);
  invitePost = signal<number | null>(null);

  shownKnown = computed(() => {
    const f = this.filter().toLowerCase();
    return this.known().filter((k) => !f || `${k.name} ${k.username}`.toLowerCase().includes(f));
  });

  ngOnInit() {
    this.appBar.setTitle('Workers');
    this.appBar.clearActions();
    if (!this.browser) return;
    this.loadKnown();
    this.loadCrew();
    this.http.get<any[]>(API + 'gigs-available/', { params: { mine: 1 } }).pipe(catchError(() => of([])))
      .subscribe((p) => { const open = p.filter((x) => x.is_open); this.openPosts.set(open); this.invitePost.set(open[0]?.id ?? null); });
    this.route.queryParamMap.subscribe((p) => {
      const q = p.get('q');
      if (q) { this.q.set(q); this.search(q); } else { this.profile.set(null); this.notFound.set(false); }
    });
  }
  ngOnDestroy() {}

  loadKnown() {
    forkJoin({
      open: this.http.get<any[]>(API + 'org-gigs-list/').pipe(catchError(() => of([]))),
      done: this.http.get<any[]>(API + 'contractor/completed-gigs/').pipe(catchError(() => of([]))),
    }).subscribe(({ open, done }) => {
      const map = new Map<string, Known>();
      [...open, ...done].forEach((g) => {
        const k = map.get(g.worker_username) || { username: g.worker_username, name: g.worker_name, gigs: 0, sites: new Set<string>(), last: g.start_date };
        k.gigs++; k.sites.add(g.organization_name); if (g.start_date > k.last) k.last = g.start_date;
        map.set(g.worker_username, k);
      });
      this.known.set([...map.values()].sort((a, b) => b.last.localeCompare(a.last)));
      this.loading.set(false);
    });
  }

  submit() {
    const q = this.q().trim();
    if (q) this.router.navigate([], { queryParams: { q } });
  }
  open(k: Known) { this.router.navigate([], { queryParams: { q: k.username } }); }
  back() { this.router.navigate([], { queryParams: {} }); }

  search(q: string) {
    this.searching.set(true);
    this.notFound.set(false);
    this.http.get<Profile>(API + 'workers/search/', { params: { q } }).subscribe({
      next: (p) => { this.profile.set(p); this.searching.set(false); },
      error: () => { this.profile.set(null); this.notFound.set(true); this.searching.set(false); },
    });
  }

  loadCrew() {
    this.http.get<any[]>(API + 'crew/').pipe(catchError(() => of([]))).subscribe((c) => this.crew.set(c));
  }

  findWorkers() {
    this.finding.set(true);
    const params: Record<string, string> = { trade: this.trade().trim(), county: this.county().trim() };
    if (this.onlyAvailable()) params['available'] = '1';
    this.http.get<any[]>(API + 'workers/available/', { params }).subscribe({
      next: (w) => { this.found.set(w); this.finding.set(false); },
      error: () => { this.found.set([]); this.finding.set(false); },
    });
  }

  toggleCrew(username: string, name: string, inCrew: boolean) {
    const req = inCrew ? this.http.delete(API + `crew/${encodeURIComponent(username)}/`) : this.http.post(API + 'crew/', { username });
    req.subscribe({
      next: () => {
        const p = this.profile();
        if (p && p.username === username) this.profile.set({ ...p, in_crew: !inCrew });
        this.found.update((l) => l && l.map((w) => (w.username === username ? { ...w, in_crew: !inCrew } : w)));
        this.loadCrew();
        this.snack.open(inCrew ? `${name} removed from your crew.` : `${name} added to your crew.`, 'OK', { duration: 2500 });
      },
      error: () => this.snack.open('Could not update your crew.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  inviteTo(username: string, name: string) {
    const id = this.invitePost(); if (!id) return;
    this.http.post<any>(API + `gigs-available/${id}/invite/`, { username }).subscribe({
      next: () => this.snack.open(`Invitation sent to ${name}.`, 'OK', { duration: 3000, panelClass: 'success-snackbar' }),
      error: (e) => this.snack.open(e?.error?.detail || 'Could not invite.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  scoreTone(s: number) { return s >= 60 ? 'ok' : s >= 30 ? 'warn' : 'danger'; }
}
