const { createApp } = Vue;

createApp({
    data() {
        return {
            tab: 'drives', profile: {}, drives: [], applications: [], interviews: [],
            toasts: [], connectionStatus: 'Connecting...', socket: null,
            appFilters: { search: '', status: '', sortBy: 'application_date' },
            debounceTimer: null,
            newDrive: { job_title: '', job_description: '', location: '', min_cgpa: 0, eligible_branches: '', eligible_year: null, application_deadline: '' },
            expanded: {},
            resumePreview: null, resumePreviewAppId: null,
            studentProfile: null,
            scheduleApp: null,
            scheduleForm: { interview_date: '', interview_time: '', interview_type: 'technical', interview_round: 1, location_or_link: '', notes: '' },
            resumeModal: null, scheduleModal: null, studentProfileModal: null
        };
    },
    mounted() {
        this.loadAll();
        this.initSocket();
        this.resumeModal = new bootstrap.Modal(document.getElementById('resumeModal'));
        this.scheduleModal = new bootstrap.Modal(document.getElementById('scheduleModal'));
        this.studentProfileModal = new bootstrap.Modal(document.getElementById('studentProfileModal'));
    },
    methods: {
        async api(url, opts = {}) {
            const res = await fetch(url, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...opts });
            if (res.status === 401) { window.location.href = '/'; return null; }
            return res.json();
        },
        async loadAll() {
            const [profile, drives, apps, ivs] = await Promise.all([
                this.api('/api/company/profile'),
                this.api('/api/company/drives'),
                this.loadApplications(),
                this.api('/api/company/interviews')
            ]);
            if (profile) this.profile = profile;
            if (drives) this.drives = drives;
            if (ivs) this.interviews = ivs;
        },
        debouncedLoadApps() {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => this.loadApplications(), 300);
        },
        async loadApplications() {
            const p = new URLSearchParams();
            if (this.appFilters.search) p.set('search', this.appFilters.search);
            if (this.appFilters.status) p.set('status', this.appFilters.status);
            if (this.appFilters.sortBy) p.set('sort_by', this.appFilters.sortBy);
            this.applications = await this.api(`/api/company/applications?${p}`) || [];
        },
        initSocket() {
            this.socket = io({ withCredentials: true });
            this.socket.on('connect', () => { this.connectionStatus = 'Live'; });
            this.socket.on('disconnect', () => { this.connectionStatus = 'Offline'; });
            this.socket.on('company_status_changed', (d) => { this.toast(`Status: ${d.status}`); this.profile.approval_status = d.status; });
            this.socket.on('drive_status_changed', (d) => { this.toast(`Drive "${d.job_title}" → ${d.status}`); this.loadAll(); });
            this.socket.on('new_application', (d) => { this.toast(`New application: ${d.student_name}`); this.loadAll(); });
            this.socket.on('notification', (d) => this.toast(d.message));
        },
        toast(msg) { this.toasts.unshift(msg); if (this.toasts.length > 5) this.toasts.pop(); },
        statusBadge(s) { return { pending: 'bg-warning text-dark', approved: 'bg-success', rejected: 'bg-danger' }[s] || 'bg-secondary'; },
        formatDate(d) { return d ? new Date(d).toLocaleDateString('en-IN', { year:'numeric', month:'short', day:'numeric' }) : 'Not set'; },
        formatSize(b) { if (!b) return '—'; return b > 1048576 ? (b/1048576).toFixed(1)+' MB' : (b/1024).toFixed(0)+' KB'; },
        async createDrive() {
            const data = await this.api('/api/company/drives', { method: 'POST', body: JSON.stringify(this.newDrive) });
            if (data) { alert(data.message); this.tab = 'drives'; this.loadAll(); }
        },
        async updateStatus(id, status) {
            if (!status) return;
            await this.api(`/api/company/applications/${id}/status`, { method: 'PUT', body: JSON.stringify({ status }) });
            this.loadApplications();
        },
        downloadResume(appId) { window.open(`/api/company/applications/${appId}/resume/download`, '_blank'); },
        async previewResume(appId) {
            this.resumePreviewAppId = appId;
            this.resumePreview = await this.api(`/api/company/applications/${appId}/resume/preview`);
            if (this.resumePreview) this.resumeModal.show();
        },
        async viewStudentProfile(appId) {
            this.studentProfile = await this.api(`/api/company/applications/${appId}/student-profile`);
            if (this.studentProfile) this.studentProfileModal.show();
        },
        openSchedule(app) {
            this.scheduleApp = app;
            this.scheduleForm = { interview_date: '', interview_time: '', interview_type: 'technical', interview_round: 1, location_or_link: '', notes: '' };
            this.scheduleModal.show();
        },
        async submitSchedule() {
            const payload = { application_id: this.scheduleApp.id, ...this.scheduleForm };
            const data = await this.api('/api/company/interviews', { method: 'POST', body: JSON.stringify(payload) });
            if (data) {
                alert(data.message);
                this.scheduleModal.hide();
                this.loadAll();
            }
        },
        toggleDesc(id) {
            this.expanded = this.expanded || {};
            this.expanded[id] = !this.expanded[id];
        },
        async completeInterview(id) {
            const feedback = prompt('Interview feedback (optional):') || '';
            await this.api(`/api/company/interviews/${id}/complete`, { method: 'PUT', body: JSON.stringify({ feedback }) });
            this.loadAll();
        },
        async cancelInterview(id) {
            if (!confirm('Cancel this interview?')) return;
            await this.api(`/api/company/interviews/${id}/cancel`, { method: 'PUT' });
            this.loadAll();
        },
        async logout() {
            await this.api('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        }
    }
}).mount('#companyApp');
