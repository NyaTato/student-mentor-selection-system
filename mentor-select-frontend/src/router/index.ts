import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSharedStore } from '@/stores/shared'

/* 学生端路由 — 对应 PROJECT.md 第 5 节 12 个页面 */
const studentRoutes: RouteRecordRaw[] = [
  {
    path: '/student',
    component: () => import('@/layouts/StudentLayout.vue'),
    meta: { requiresAuth: true, role: 'STUDENT' },
    children: [
      { path: '', redirect: '/student/dashboard' },
      { path: 'dashboard', name: 'StudentDashboard', component: () => import('@/views/student/DashboardView.vue') },
      { path: 'personal-info', name: 'StudentPersonalInfo', component: () => import('@/views/student/PersonalInfoView.vue') },
      { path: 'teachers', name: 'StudentTeacherList', component: () => import('@/views/student/TeacherListView.vue') },
      { path: 'first-round/apply', name: 'StudentFirstRoundApply', component: () => import('@/views/student/FirstRoundApplyView.vue') },
      { path: 'first-round/my', name: 'StudentMyFirstRound', component: () => import('@/views/student/MyFirstRoundView.vue') },
      { path: 'first-round/result', name: 'StudentFirstRoundResult', component: () => import('@/views/student/FirstRoundResultView.vue') },
      { path: 'second-round/teachers', name: 'StudentSecondRoundTeacherList', component: () => import('@/views/student/SecondRoundTeacherListView.vue') },
      { path: 'second-round/my', name: 'StudentMySecondRound', component: () => import('@/views/student/MySecondRoundView.vue') },
      { path: 'final-result', name: 'StudentFinalResult', component: () => import('@/views/student/FinalResultView.vue') },
      { path: 'history', name: 'StudentHistory', component: () => import('@/views/student/HistoryView.vue') },
    ],
  },
]

/* 导师端路由 — 对应 PROJECT.md 第 6 节 7 个页面 */
const teacherRoutes: RouteRecordRaw[] = [
  {
    path: '/teacher',
    component: () => import('@/layouts/TeacherLayout.vue'),
    meta: { requiresAuth: true, role: 'TEACHER' },
    children: [
      { path: '', redirect: '/teacher/dashboard' },
      { path: 'dashboard', name: 'TeacherDashboard', component: () => import('@/views/teacher/DashboardView.vue') },
      { path: 'applications', name: 'TeacherApplicationList', component: () => import('@/views/teacher/ApplicationListView.vue') },
      { path: 'admission', name: 'TeacherAdmissionManagement', component: () => import('@/views/teacher/AdmissionManagementView.vue') },
      { path: 'assigned-students', name: 'TeacherAssignedStudents', component: () => import('@/views/teacher/AssignedStudentsView.vue') },
      { path: 'quota', name: 'TeacherQuotaOverview', component: () => import('@/views/teacher/QuotaOverviewView.vue') },
      { path: 'personal-info', name: 'TeacherPersonalInfo', component: () => import('@/views/teacher/PersonalInfoView.vue') },
    ],
  },
]

/* 管理员端路由 — 对应 PROJECT.md 第 7 节 17 个页面（含新增 6 页） */
const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, role: 'ADMIN' },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'AdminDashboard', component: () => import('@/views/admin/DashboardView.vue') },
      { path: 'students', name: 'AdminStudentManagement', component: () => import('@/views/admin/StudentManagementView.vue') },
      { path: 'teachers', name: 'AdminTeacherManagement', component: () => import('@/views/admin/TeacherManagementView.vue') },
      { path: 'administrators', name: 'AdminAdminManagement', component: () => import('@/views/admin/AdminManagementView.vue') },
      { path: 'system-state', name: 'AdminSystemStateControl', component: () => import('@/views/admin/SystemStateControlView.vue') },
      { path: 'schedule', name: 'AdminScheduleManagement', component: () => import('@/views/admin/ScheduleManagementView.vue') },
      { path: 'assignment-results', name: 'AdminAssignmentResults', component: () => import('@/views/admin/AssignmentResultsView.vue') },
      { path: 'announcements', name: 'AdminAnnouncementManagement', component: () => import('@/views/admin/AnnouncementManagementView.vue') },
      { path: 'manual-assignment', name: 'AdminManualAssignment', component: () => import('@/views/admin/ManualAssignmentView.vue') },
      { path: 'auto-assignment', name: 'AdminAutoAssignment', component: () => import('@/views/admin/AutomaticAssignmentView.vue') },
      { path: 'auto-assignment-result', name: 'AdminAutoAssignmentResult', component: () => import('@/views/admin/AutomaticAssignmentResultView.vue') },
      { path: 'academic-year', name: 'AdminAcademicYearManagement', component: () => import('@/views/admin/AcademicYearManagementView.vue') },
      { path: 'excel-import', name: 'AdminExcelImport', component: () => import('@/views/admin/ExcelImportView.vue') },
      { path: 'import-result', name: 'AdminImportResult', component: () => import('@/views/admin/ImportResultView.vue') },
      { path: 'logs', name: 'AdminSystemLogs', component: () => import('@/views/admin/SystemLogsView.vue') },
      { path: 'monitoring', name: 'AdminSystemMonitoring', component: () => import('@/views/admin/SystemMonitoringView.vue') },
    ],
  },
]

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue') },
  ...studentRoutes,
  ...teacherRoutes,
  ...adminRoutes,
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/* 路由守卫 */
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  const sharedStore = useSharedStore()

  if (to.meta.requiresAuth) {
    if (!authStore.isAuthenticated) {
      next('/login')
      return
    }
    /* 已认证但当前角色数据尚未加载 — 按角色从后端加载（只请求有权访问的数据） */
    if (!sharedStore.isLoaded || sharedStore.loadedRole !== authStore.user?.role) {
      try {
        await sharedStore.loadFromServer(authStore.user?.role ?? null)
      } catch {
        /* 加载失败不阻塞导航 */
      }
    }
    if (to.meta.role && authStore.userRole !== to.meta.role) {
      next(authStore.homePath)
      return
    }
  }

  if (to.name === 'Login' && authStore.isAuthenticated) {
    next(authStore.homePath)
    return
  }

  next()
})

export default router
