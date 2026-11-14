import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';

const API = environment.apiUrl + 'api/';
interface JobType { id: number; name: string; code: string; organization: number; }

@Component({
  selector: 'app-add-gig-types',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './add-gig-types.html',
  styleUrl: './add-gig-types.css',
})
export class AddGigTypes implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  ctx = inject(SiteContextService);

  sites = signal<{ id: number; name: string }[]>([]);
  siteId = signal<number | null>(null);
  types = signal<JobType[]>([]);
  usage = signal<Record<number, number>>({});
  loading = signal(true);
  newName = signal('');
  adding = signal(false);
  q = signal('');

  shown = computed(() => {
    const q = this.q().toLowerCase();
    return this.types().filter((t) => !q || t.name.toLowerCase().includes(q)).sort((a, b) => a.name.localeCompare(b.name));
  });
  siteName = computed(() => this.sites().find((s) => s.id === this.siteId())?.name ?? '');

  constructor() {
    effect(() => { const id = this.ctx.id(); if (id !== null && id !== this.siteId()) this.pick(id); });
  }

  ngOnInit() {
    this.appBar.setTitle('Job types');
    this.appBar.clearActions();
    if (!this.browser) return;
    this.http.get<any[]>(API + 'user-organizations/').pipe(catchError(() => of([]))).subscribe((s) => {
      this.sites.set(s.map((x) => ({ id: x.id, name: x.name })));
      const first = this.ctx.id() ?? s[0]?.id ?? null;
      if (first !== null) this.pick(first); else this.loading.set(false);
    });
    this.http.get<any[]>(API + 'org-gigs-list/').pipe(catchError(() => of([]))).subscribe((g) => {
      const u: Record<number, number> = {};
      g.forEach((x) => (u[x.job_type] = (u[x.job_type] || 0) + 1));
      this.usage.set(u);
    });
  }

  pick(id: number) {
    this.siteId.set(+id);
    this.loading.set(true);
    this.http.get<JobType[]>(API + 'job-types/', { params: { organization: id } }).subscribe({
      next: (t) => { this.types.set(t); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  add() {
    const name = this.newName().trim();
    if (!name || this.siteId() === null) return;
    if (this.types().some((t) => t.name.toLowerCase() === name.toLowerCase())) {
      this.snack.open(`${name} already exists at this site.`, 'OK', { duration: 3000 }); return;
    }
    this.adding.set(true);
    this.http.post<JobType>(API + 'job-types/', { name, organization: this.siteId() }).subscribe({
      next: (t) => { this.types.update((l) => [...l, t]); this.newName.set(''); this.adding.set(false);
        this.snack.open(`${t.name} added.`, 'OK', { duration: 2500, panelClass: 'success-snackbar' }); },
      error: (e) => { this.adding.set(false); this.snack.open(e?.error?.detail || 'Could not add the job type.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  remove(t: JobType) {
    if ((this.usage()[t.id] || 0) > 0 && !confirm(`${t.name} is used by ${this.usage()[t.id]} open gig(s). Deleting it also deletes those gigs. Continue?`)) return;
    this.http.delete(API + `job-types/${t.id}/`).subscribe({
      next: () => { this.types.update((l) => l.filter((x) => x.id !== t.id)); this.snack.open(`${t.name} removed.`, 'OK', { duration: 2500 }); },
      error: (e) => this.snack.open(e?.error?.error || 'Could not delete.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }
}
