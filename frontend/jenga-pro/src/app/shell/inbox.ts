// Persisted notifications (the bell's "Recent" list). Canonical: frontend/design-system/shell/inbox.ts
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, of } from 'rxjs';
import { environment } from '../../environments/environment';
import { ShellNotification } from './types';

const ICONS: Record<string, [string, ShellNotification['tone']]> = {
  gig_verified: ['task_alt', 'ok'], gig_rejected: ['block', 'danger'], gig_completed: ['done_all', 'ok'],
  application_accepted: ['celebration', 'ok'], application_declined: ['info', 'info'], new_applicant: ['front_hand', 'info'],
  invitation: ['mail', 'info'], invitation_accepted: ['celebration', 'ok'], invitation_declined: ['info', 'info'],
  job_alert: ['campaign', 'info'], id_approved: ['verified_user', 'ok'], id_rejected: ['error', 'danger'],
  incident: ['health_and_safety', 'danger'], incident_resolved: ['health_and_safety', 'ok'], site_rated: ['star', 'info'],
};

export const timeAgo = (iso: string) => {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  if (m < 1440) return `${Math.round(m / 60)}h`;
  return `${Math.round(m / 1440)}d`;
};

@Injectable({ providedIn: 'root' })
export class InboxService {
  private http = inject(HttpClient);
  private api = environment.apiUrl + 'api/notifications/';

  recent(): Observable<ShellNotification[]> {
    return this.http.get<{ unread: number; items: any[] }>(this.api).pipe(
      map((r) => r.items.slice(0, 15).map((n) => {
        const [icon, tone] = ICONS[n.kind] || ['notifications', 'info'];
        return { icon, tone, title: n.title, sub: n.body, route: n.link || '', unread: !n.is_read, time: timeAgo(n.created_at) };
      })),
      catchError(() => of([])));
  }

  markAllRead(): Observable<unknown> {
    return this.http.post(this.api + 'read/', {}).pipe(catchError(() => of(null)));
  }
}
