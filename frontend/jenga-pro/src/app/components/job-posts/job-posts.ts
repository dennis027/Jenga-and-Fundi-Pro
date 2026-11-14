import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';
import { daysAgo } from '../../shell/ui';

const API = environment.apiUrl + 'api/';

@Component({
  selector: 'app-job-posts',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './job-posts.html',
  styleUrl: './job-posts.css',
})
export class JobPosts implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  ctx = inject(SiteContextService);
  daysAgo = daysAgo;
  @ViewChild('postDialog') dialog?: ElementRef<HTMLDialogElement>;
  @ViewChild('appsDialog') appsDialog?: ElementRef<HTMLDialogElement>;
  viewing = signal<any | null>(null);
  applicants = signal<any[]>([]);
  appsLoading = signal(false);
  initials = (n: string) => (n || '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase();

  loading = signal(true);
  posts = signal<any[]>([]);
  sites = signal<any[]>([]);
  saving = signal(false);
  form = { organization: null as number | null, title: '', description: '', positions: 1 };
  crew = signal<any[]>([]);
  inviting = signal<string | null>(null);
  invitable = computed(() => {
    const taken = new Set(this.applicants().map((a) => a.worker.username));
    return this.crew().filter((c) => !taken.has(c.username));
  });

  shown = computed(() => this.posts().filter((p) => this.ctx.id() === null || p.organization === this.ctx.id()));

  ngOnInit() {
    this.appBar.setTitle('Job posts');
    this.appBar.clearActions();
    if (!this.browser) return;
    this.load();
    if (this.route.snapshot.queryParamMap.get('new')) setTimeout(() => this.openNew(), 300);
  }

  load() {
    forkJoin({
      posts: this.http.get<any[]>(API + 'gigs-available/', { params: { mine: 1 } }).pipe(catchError(() => of([]))),
      sites: this.http.get<any[]>(API + 'user-organizations/').pipe(catchError(() => of([]))),
    }).subscribe((r) => { this.posts.set(r.posts); this.sites.set(r.sites.filter((s) => s.is_active)); this.loading.set(false); });
  }

  openNew() {
    this.form = { organization: this.ctx.id() ?? this.sites()[0]?.id ?? null, title: '', description: '', positions: 1 };
    this.dialog?.nativeElement.showModal();
  }
  close() { this.dialog?.nativeElement.close(); }

  save() {
    const site = this.sites().find((s) => s.id === this.form.organization);
    if (!site || !this.form.title.trim()) return;
    this.saving.set(true);
    this.http.post<any>(API + 'gigs-available/', {
      organization: site.id, title: this.form.title.trim(), description: this.form.description.trim(), positions: Math.max(1, Math.min(50, +this.form.positions || 1)),
      county: site.county, constituency: site.constituency, ward: site.ward,
    }).subscribe({
      next: (p) => { this.saving.set(false); this.close(); this.posts.update((l) => [{ ...p, organization_name: site.name }, ...l]);
        this.snack.open('Job posted. Fundis can see it under Find work.', 'OK', { duration: 3500, panelClass: 'success-snackbar' }); },
      error: () => { this.saving.set(false); this.snack.open('Could not post the job.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  openApplicants(p: any) {
    this.viewing.set(p); this.applicants.set([]); this.appsLoading.set(true);
    this.appsDialog?.nativeElement.showModal();
    this.http.get<any[]>(API + `gigs-available/${p.id}/applications/`).subscribe({
      next: (a) => { this.applicants.set(a); this.appsLoading.set(false); }, error: () => this.appsLoading.set(false),
    });
    this.http.get<any[]>(API + 'crew/').pipe(catchError(() => of([]))).subscribe((c) => this.crew.set(c));
  }
  closeApplicants() { this.appsDialog?.nativeElement.close(); }

  decide(a: any, status: 'accepted' | 'declined') {
    this.http.post<any>(API + `applications/${a.id}/decide/`, { status }).subscribe({
      next: (r) => {
        this.applicants.update((l) => l.map((x) => (x.id === a.id ? r : x)));
        this.syncPost();
        this.snack.open(status === 'accepted' ? `${a.worker.name} accepted. Call them to agree the start.` : 'Declined.', 'OK', { duration: 3000, panelClass: status === 'accepted' ? 'success-snackbar' : '' });
      },
      error: () => this.snack.open('Could not save your decision.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  private syncPost() {
    const pending = this.applicants().filter((x) => x.status === 'pending').length;
    const filled = this.applicants().filter((x) => x.status === 'accepted').length;
    this.posts.update((l) => l.map((p) => (p.id === this.viewing()?.id
      ? { ...p, applications_count: pending, filled, is_open: p.is_open && filled < p.positions } : p)));
  }

  invite(c: any) {
    const p = this.viewing(); if (!p) return;
    this.inviting.set(c.username);
    this.http.post<any>(API + `gigs-available/${p.id}/invite/`, { username: c.username }).subscribe({
      next: (a) => { this.inviting.set(null); this.applicants.update((l) => [a, ...l]);
        this.snack.open(`Invitation sent to ${c.name}.`, 'OK', { duration: 3000, panelClass: 'success-snackbar' }); },
      error: (e) => { this.inviting.set(null); this.snack.open(e?.error?.detail || 'Could not invite.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  toggleOpen(p: any) {
    this.http.post<any>(API + `gigs-available/${p.id}/toggle/`, { is_open: !p.is_open }).subscribe({
      next: (r) => { this.posts.update((l) => l.map((x) => (x.id === p.id ? { ...x, ...r, organization_name: x.organization_name } : x)));
        this.snack.open(r.is_open ? 'Post reopened. Fundis can apply again.' : 'Post closed. It no longer shows under Find work.', 'OK', { duration: 3000 }); },
      error: (e) => this.snack.open(e?.error?.detail || 'Could not update the post.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  remove(p: any) {
    if (!confirm(`Remove “${p.title}”? Fundis will no longer see it.`)) return;
    this.http.delete(API + `gigs-available/${p.id}/`).subscribe({
      next: () => { this.posts.update((l) => l.filter((x) => x.id !== p.id)); this.snack.open('Post removed.', 'OK', { duration: 2500 }); },
      error: () => this.snack.open('Could not remove the post.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }
}
