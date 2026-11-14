import { ShellConfig } from './types';

export const SHELL_CONFIG: ShellConfig = {
  brand: 'Jenga Pro',
  brandIcon: 'apartment',
  tagline: 'Contractor portal',
  sections: [
    { title: 'Overview', items: [{ label: 'Dashboard', icon: 'space_dashboard', route: '/main-menu', exact: true }] },
    {
      title: 'Work',
      items: [
        { label: 'Verify gigs', icon: 'fact_check', route: '/main-menu/verify-gigs', badge: 'pending' },
        { label: 'All gigs', icon: 'work_history', route: '/main-menu/all-gigs' },
        { label: 'Workers', icon: 'engineering', route: '/main-menu/manage-workers' },
        { label: 'Site safety', icon: 'health_and_safety', route: '/main-menu/safety' },
      ],
    },
    {
      title: 'Sites',
      items: [
        { label: 'Sites', icon: 'apartment', route: '/main-menu/add-sites' },
        { label: 'Job types', icon: 'category', route: '/main-menu/add-gig-type' },
        { label: 'Job posts', icon: 'campaign', route: '/main-menu/job-posts' },
      ],
    },
    { title: 'Money', items: [
      { label: 'Payroll & attendance', icon: 'request_quote', route: '/main-menu/workforce' },
      { label: 'M-Pesa payments', icon: 'payments', route: '/main-menu/MPESA-Payments' },
    ] },
    { title: 'Insights', items: [
      { label: 'Analytics', icon: 'monitoring', route: '/main-menu/analytics' },
      { label: 'Activity', icon: 'history', route: '/main-menu/activity' },
    ] },
  ],
  quickActions: [
    { label: 'Verify pending gigs', icon: 'fact_check', route: '/main-menu/verify-gigs' },
    { label: 'Add a site', icon: 'add_business', route: '/main-menu/add-sites?new=1' },
    { label: 'Find a worker', icon: 'person_search', route: '/main-menu/manage-workers' },
    { label: 'Post a job', icon: 'campaign', route: '/main-menu/job-posts?new=1' },
    { label: 'Pay with M-Pesa', icon: 'payments', route: '/main-menu/MPESA-Payments' },
    { label: 'Weekly payroll', icon: 'request_quote', route: '/main-menu/workforce' },
    { label: 'Attendance register', icon: 'location_on', route: '/main-menu/workforce?tab=attendance' },
    { label: 'Site budgets', icon: 'savings', route: '/main-menu/workforce?tab=budgets' },
    { label: 'My crew', icon: 'star', route: '/main-menu/manage-workers' },
    { label: 'Safety incidents', icon: 'health_and_safety', route: '/main-menu/safety' },
    { label: 'My profile', icon: 'person', route: '/main-menu/profile' },
  ],
  searchAction: (q) => ({ label: `Find worker “${q}”`, icon: 'person_search', hint: 'Workers',
                          route: `/main-menu/manage-workers?q=${encodeURIComponent(q)}` }),
};
