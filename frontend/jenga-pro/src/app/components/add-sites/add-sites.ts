import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import regionsData from '../../../assets/JSON-Files/regions.json';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';

const API = environment.apiUrl + 'api/';
interface County { county_name: string; constituencies: { constituency_name: string; wards: string[] }[]; }
interface Site { id: number; name: string; description: string | null; phone_number: string | null; county: string; constituency: string; ward: string; is_active: boolean; }
interface SiteStats { open: number; pending: number; workers: number; }

@Component({
  selector: 'app-add-sites',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './add-sites.html',
  styleUrl: './add-sites.css',
})
export class AddSites implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private site = inject(SiteContextService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  @ViewChild('siteDialog') dialog?: ElementRef<HTMLDialogElement>;

  regions = ((regionsData as any).counties || regionsData) as County[];
  loading = signal(true);
  sites = signal<Site[]>([]);
  stats = signal<Record<number, SiteStats>>({});
  editing = signal<Site | null>(null);
  saving = signal(false);
  form = { name: '', description: '', phone_number: '', county: '', constituency: '', ward: '' };

  totals = computed(() => {
    const s = Object.values(this.stats());
    return { sites: this.sites().length, active: this.sites().filter((x) => x.is_active).length,
             open: s.reduce((a, b) => a + b.open, 0), pending: s.reduce((a, b) => a + b.pending, 0) };
  });

  get constituencies() { return this.regions.find((c) => c.county_name === this.form.county)?.constituencies ?? []; }
  get wards() { return this.constituencies.find((c) => c.constituency_name === this.form.constituency)?.wards ?? []; }

  ngOnInit() {
    this.appBar.setTitle('Sites');
    this.appBar.clearActions();
    if (!this.browser) return;
    this.load();
    this.route.queryParamMap.subscribe((p) => { if (p.get('new')) setTimeout(() => this.openNew()); });
  }

  load() {
    forkJoin({
      sites: this.http.get<Site[]>(API + 'user-organizations/').pipe(catchError(() => of([]))),
      gigs: this.http.get<any[]>(API + 'org-gigs-list/').pipe(catchError(() => of([]))),
    }).subscribe(({ sites, gigs }) => {
      const st: Record<number, SiteStats> = {};
      sites.forEach((s) => (st[s.id] = { open: 0, pending: 0, workers: 0 }));
      const workers: Record<number, Set<number>> = {};
      gigs.forEach((g) => {
        const s = st[g.organization]; if (!s) return;
        s.open++; if (!g.is_verified) s.pending++;
        (workers[g.organization] ||= new Set()).add(g.worker);
      });
      Object.entries(workers).forEach(([id, w]) => (st[+id].workers = w.size));
      this.sites.set(sites);
      this.stats.set(st);
      this.loading.set(false);
    });
  }

  openNew() {
    this.editing.set(null);
    this.form = { name: '', description: '', phone_number: '', county: '', constituency: '', ward: '' };
    this.dialog?.nativeElement.showModal();
  }
  openEdit(s: Site) {
    this.editing.set(s);
    this.form = { name: s.name, description: (s.description || '').replace(/^\[demo\]\s*/, ''), phone_number: s.phone_number || '',
                  county: s.county, constituency: s.constituency, ward: s.ward };
    this.dialog?.nativeElement.showModal();
  }
  close() {
    this.dialog?.nativeElement.close();
    if (this.route.snapshot.queryParamMap.get('new')) this.router.navigate([], { queryParams: {} });
  }
  countyChanged() { this.form.constituency = ''; this.form.ward = ''; }
  constituencyChanged() { this.form.ward = ''; }
  valid() { return this.form.name.trim() && this.form.county && this.form.constituency && this.form.ward; }

  save() {
    if (!this.valid()) return;
    this.saving.set(true);
    const e = this.editing();
    const req = e ? this.http.put<Site>(API + `organizations/${e.id}/`, this.form) : this.http.post<Site>(API + 'organizations/', this.form);
    req.subscribe({
      next: () => {
        this.saving.set(false);
        this.close();
        this.snack.open(e ? 'Site updated.' : `${this.form.name} added. Workers can now log gigs there.`, 'OK', { duration: 3500, panelClass: 'success-snackbar' });
        this.load();
      },
      error: (err) => {
        this.saving.set(false);
        this.snack.open(err?.error?.detail || 'Could not save the site.', 'OK', { duration: 4000, panelClass: 'error-snackbar' });
      },
    });
  }

  toggleActive(s: Site) {
    this.http.post<any>(API + `organizations/${s.id}/toggle-active/`, {}).subscribe({
      next: () => {
        this.sites.update((l) => l.map((x) => (x.id === s.id ? { ...x, is_active: !x.is_active } : x)));
        this.snack.open(s.is_active ? `${s.name} paused. Workers can't log new gigs there.` : `${s.name} is active again.`, 'OK', { duration: 3500 });
      },
      error: () => this.snack.open('Could not change the site status.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  workIn(s: Site, page: string) {
    this.site.select(s.id, s.name);
    this.router.navigate(['/main-menu', page]);
  }
}
