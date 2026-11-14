import { I18nService, TPipe } from '../../services/i18n';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { daysAgo } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
interface Post {
  id: number; title: string; description: string; county: string; constituency: string; ward: string; created_at: string;
  organization: number; organization_name: string; organization_phone: string | null;
  my_application: { id: number; status: string } | null; positions: number; filled: number; saved: boolean;
  site_rating: { avg: number; count: number } | null;
}
interface Alert { id: number; keyword: string; county: string; sms: boolean; }
type Tab = 'open' | 'saved' | 'applied';

@Component({
  selector: 'app-search-gigs',
  standalone: true,
  imports: [TPipe, CommonModule, FormsModule, RouterModule],
  templateUrl: './search-gigs.html',
  styleUrl: './search-gigs.css',
})
export class SearchGigs implements OnInit {
  private i18n = inject(I18nService);
  private http = inject(HttpClient);
  private appBar = inject(AppBarService);
  private snack = inject(MatSnackBar);
  @ViewChild('applyDialog') dialog?: ElementRef<HTMLDialogElement>;
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  daysAgo = daysAgo;

  loading = signal(true);
  posts = signal<Post[]>([]);
  saved = signal<Post[]>([]);
  q = signal('');
  county = signal('');
  tab = signal<Tab>('open');
  apps = signal<any[]>([]);
  alerts = signal<Alert[]>([]);
  applying = signal<Post | null>(null);
  note = signal('');
  sending = signal(false);
  alertKeyword = signal('');
  alertCounty = signal('');
  alertSms = signal(false);
  showAlerts = signal(false);

  accepted = computed(() => this.apps().filter((a) => a.status === 'accepted'));
  invitations = computed(() => this.apps().filter((a) => a.status === 'invited'));
  applied = computed(() => this.apps().filter((a) => a.status !== 'invited'));
  counties = computed(() => [...new Set(this.posts().map((p) => p.county))].sort());
  shown = computed(() => {
    const q = this.q().toLowerCase();
    const list = this.tab() === 'saved' ? this.saved() : this.posts();
    return list.filter((p) => (!this.county() || p.county === this.county())
      && (!q || `${p.title} ${p.description} ${p.organization_name} ${p.ward} ${p.constituency}`.toLowerCase().includes(q)));
  });

  ngOnInit() {
    this.appBar.setTitle('Find work');
    this.appBar.clearActions();
    if (this.browser) this.load();
  }

  load() {
    forkJoin({
      posts: this.http.get<Post[]>(API + 'gigs-available/').pipe(catchError(() => of([]))),
      saved: this.http.get<Post[]>(API + 'saved-posts/').pipe(catchError(() => of([]))),
      apps: this.http.get<any[]>(API + 'my-applications/').pipe(catchError(() => of([]))),
      alerts: this.http.get<Alert[]>(API + 'job-alerts/').pipe(catchError(() => of([]))),
    }).subscribe((r) => {
      this.posts.set(r.posts); this.saved.set(r.saved); this.apps.set(r.apps); this.alerts.set(r.alerts);
      this.loading.set(false);
    });
  }

  private ok(msg: string) { this.snack.open(msg, this.i18n.t('OK'), { duration: 3500, panelClass: 'success-snackbar' }); }
  private fail(e: any, fallback: string) {
    this.snack.open(e?.error?.detail || e?.error?.non_field_errors?.[0] || this.i18n.t(fallback), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' });
  }

  openApply(p: Post) { this.applying.set(p); this.note.set(''); this.dialog?.nativeElement.showModal(); }
  closeApply() { this.dialog?.nativeElement.close(); }

  apply() {
    const p = this.applying(); if (!p) return;
    this.sending.set(true);
    this.http.post<any>(API + `gigs-available/${p.id}/apply/`, { message: this.note().trim() }).subscribe({
      next: (a) => {
        this.sending.set(false); this.closeApply();
        const upd = (l: Post[]) => l.map((x) => (x.id === p.id ? { ...x, my_application: { id: a.id, status: a.status } } : x));
        this.posts.update(upd); this.saved.update(upd);
        this.apps.update((l) => [a, ...l.filter((x) => x.id !== a.id)]);
        this.ok(this.i18n.t('Sent to {0}. You\'ll see their answer here.', p.organization_name));
      },
      error: (e) => { this.sending.set(false); this.fail(e, 'Could not send.'); },
    });
  }

  toggleSave(p: Post) {
    this.http.post<{ saved: boolean }>(API + `gigs-available/${p.id}/save/`, {}).subscribe({
      next: (r) => {
        const upd = (l: Post[]) => l.map((x) => (x.id === p.id ? { ...x, saved: r.saved } : x));
        this.posts.update(upd);
        this.saved.update((l) => r.saved ? [{ ...p, saved: true }, ...l] : l.filter((x) => x.id !== p.id));
      },
      error: (e) => this.fail(e, 'Could not save.'),
    });
  }

  withdraw(a: any) {
    if (!confirm(this.i18n.t('Withdraw your application for “{0}”?', a.post_title))) return;
    this.http.post<any>(API + `applications/${a.id}/withdraw/`, {}).subscribe({
      next: (r) => {
        this.apps.update((l) => l.map((x) => (x.id === a.id ? r : x)));
        const upd = (l: Post[]) => l.map((x) => (x.id === a.post ? { ...x, my_application: { id: r.id, status: r.status } } : x));
        this.posts.update(upd); this.saved.update(upd);
        this.ok(this.i18n.t('Application withdrawn.'));
      },
      error: (e) => this.fail(e, 'Could not withdraw.'),
    });
  }

  respond(a: any, accept: boolean) {
    this.http.post<any>(API + `applications/${a.id}/respond/`, { accept }).subscribe({
      next: (r) => {
        this.apps.update((l) => l.map((x) => (x.id === a.id ? r : x)));
        this.ok(accept ? this.i18n.t('You accepted. Call {0} to agree the start.', a.site) : this.i18n.t('Invitation declined.'));
      },
      error: (e) => this.fail(e, 'Could not send.'),
    });
  }

  addAlert() {
    const body = { keyword: this.alertKeyword().trim(), county: this.alertCounty().trim(), sms: this.alertSms() };
    this.http.post<Alert>(API + 'job-alerts/', body).subscribe({
      next: (a) => { this.alerts.update((l) => [a, ...l]); this.alertKeyword.set(''); this.alertCounty.set(''); this.alertSms.set(false); this.ok(this.i18n.t('Job alert saved.')); },
      error: (e) => this.fail(e, 'Could not save.'),
    });
  }

  removeAlert(a: Alert) {
    this.http.delete(API + `job-alerts/${a.id}/`).subscribe(() => this.alerts.update((l) => l.filter((x) => x.id !== a.id)));
  }

  statusLabel(s: string) {
    return ({ pending: 'Applied', accepted: 'Accepted', declined: 'Not this time', withdrawn: 'Withdrawn', invited: 'Invited' } as any)[s] || s;
  }
  statusTone(s: string) { return ({ pending: 'warn', accepted: 'ok', invited: 'info' } as any)[s] || ''; }
}
