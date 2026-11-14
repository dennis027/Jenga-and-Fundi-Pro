import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';
import { environment } from '../../environments/environment';
import { ShellData, ShellNotification, ShellUser } from './types';

const API = environment.apiUrl + 'api/';

@Injectable({ providedIn: 'root' })
export class ShellDataService implements ShellData {
  private http = inject(HttpClient);

  user(): Observable<ShellUser> {
    return this.http.get<any>(API + 'user/').pipe(map((u) => ({
      name: u.full_name || u.username, subtitle: `Credit score ${u.credit_score ?? 0}/100`,
      picture: u.profile_pic ? (/^https?:/.test(u.profile_pic) ? u.profile_pic : environment.apiUrl + u.profile_pic.replace(/^\//, '')) : null,
    })));
  }

  badges(): Observable<Record<string, number>> {
    return this.http.get<any[]>(API + 'user-gigs/').pipe(
      map((g) => ({ ready: g.filter((x) => x.is_verified).length })), catchError(() => of({})));
  }

  notifications(): Observable<ShellNotification[]> {
    return forkJoin({
      gigs: this.http.get<any[]>(API + 'user-gigs/').pipe(catchError(() => of([]))),
      me: this.http.get<any>(API + 'user/').pipe(catchError(() => of(null))),
      apps: this.http.get<any[]>(API + 'my-applications/').pipe(catchError(() => of([]))),
    }).pipe(map(({ gigs, me, apps }) => {
      const out: ShellNotification[] = [];
      apps.filter((a: any) => a.status === 'accepted').forEach((a: any) => out.push({ icon: 'celebration', tone: 'ok',
        title: `${a.site} accepted you`, sub: `For “${a.post_title}”. Call them to agree the start`, route: '/main-menu/search-gigs' }));
      const ready = gigs.filter((g) => g.is_verified);
      const waiting = gigs.filter((g) => !g.is_verified);
      ready.forEach((g) => out.push({ icon: 'task_alt', tone: 'ok', title: `${g.job_type_name || 'Gig'} at ${g.organization_name || g.client_name} was verified`,
        sub: 'Mark it complete to earn +5 points', route: '/main-menu/gig-summary' }));
      if (waiting.length) out.push({ icon: 'hourglass_top', tone: 'warn', title: `${waiting.length} gig${waiting.length > 1 ? 's' : ''} waiting for the contractor`,
        sub: 'You will be notified once verified', route: '/main-menu/gig-summary' });
      if (me && !me.id_verified) out.push({ icon: 'verified_user', tone: 'info', title: 'Verify your ID',
        sub: 'Adds +20 to your credit score', route: '/main-menu/verification-status' });
      return out;
    }));
  }
}
