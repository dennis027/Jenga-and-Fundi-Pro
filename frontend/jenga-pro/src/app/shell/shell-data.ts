import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';
import { environment } from '../../environments/environment';
import { ShellContext, ShellData, ShellNotification, ShellUser } from './types';

const API = environment.apiUrl + 'api/';

@Injectable({ providedIn: 'root' })
export class ShellDataService implements ShellData {
  private http = inject(HttpClient);
  contextLabel = 'Your sites';

  user(): Observable<ShellUser> {
    return this.http.get<any>(API + 'user/').pipe(map((u) => ({
      name: u.full_name || u.username, subtitle: 'Contractor · ' + (u.email || u.username),
      picture: u.profile_pic ? (/^https?:/.test(u.profile_pic) ? u.profile_pic : environment.apiUrl + u.profile_pic.replace(/^\//, '')) : null,
    })));
  }

  badges(): Observable<Record<string, number>> {
    return this.http.get<any[]>(API + 'contractor/dashboard/unverified-gigs/').pipe(
      map((g) => ({ pending: g.length })), catchError(() => of({})));
  }

  notifications(): Observable<ShellNotification[]> {
    return forkJoin({
      pending: this.http.get<any[]>(API + 'contractor/dashboard/unverified-gigs/').pipe(catchError(() => of([]))),
      disputes: this.http.get<any[]>(API + 'disputes/').pipe(catchError(() => of([]))),
    }).pipe(map(({ pending, disputes }) => {
      const out: ShellNotification[] = pending.slice(0, 5).map((g) => ({
        icon: 'fact_check', tone: 'warn' as const, title: `${g.workerName} logged ${g.jobType}`,
        sub: `${g.siteName} · ${g.duration} · waiting for you`, route: '/main-menu/verify-gigs',
      }));
      if (pending.length > 5) out.push({ icon: 'more_horiz', tone: 'info', title: `${pending.length - 5} more gigs to verify`, sub: 'Open the verification queue', route: '/main-menu/verify-gigs' });
      disputes.filter((d) => d.status === 'open').forEach((d) => out.push({
        icon: 'gavel', tone: 'danger', title: 'A worker disputed a gig', sub: d.reason, route: '/main-menu/all-gigs',
      }));
      return out;
    }));
  }

  contexts(): Observable<ShellContext[]> {
    return this.http.get<any[]>(API + 'user-organizations/').pipe(map((orgs) => orgs.map((o) => ({ id: o.id, label: o.name }))));
  }
}
