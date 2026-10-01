<template>
  <div class="flex flex-col h-full overflow-hidden bg-surface-base">
    <!-- Top Header -->
    <LayoutHeader>
      <template #left-header>
        <div class="flex items-center gap-2">
          <div class="p-1.5 rounded-lg bg-surface-gray-2 text-ink-gray-9">
            <MegaphoneIcon class="size-4 text-ink-gray-7" />
          </div>
          <h1 class="text-base sm:text-lg font-semibold text-ink-gray-9 leading-none whitespace-nowrap">
            {{ __('Facebook Marketing') }}
          </h1>
        </div>
      </template>
      <template #right-header>
        <div class="flex items-center gap-2 flex-nowrap shrink-0">
          <Button
            variant="ghost"
            :iconLeft="LucideRefreshCcw"
            :loading="loading"
            :title="__('Làm mới')"
            @click="fetchPosts"
          >
            <span class="hidden sm:inline">{{ __('Làm mới') }}</span>
          </Button>

          <Dropdown :options="batchActions">
            <Button
              variant="subtle"
              :label="__('Thao tác tuần')"
              iconRight="chevron-down"
            />
          </Dropdown>

          <Button
            variant="solid"
            :iconLeft="LucideCalendarPlus"
            @click="showGenerateModal = true"
          >
            {{ __('Lên kế hoạch tuần') }}
          </Button>

          <Button
            variant="subtle"
            :iconLeft="LucidePlus"
            @click="openCreateModal"
          >
            {{ __('Tạo bài mới') }}
          </Button>
        </div>
      </template>
    </LayoutHeader>

    <!-- Main Content Area -->
    <div class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
      <!-- Multi-Agent Pipeline Status Banner (When recently run or toggleable) -->
      <div
        v-if="pipelineSteps.length"
        class="rounded-xl border border-outline-gray-1 bg-surface-gray-1 p-4 shadow-xs"
      >
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <LucideCheckCheck class="size-4 text-emerald-600" />
            <h3 class="text-sm font-semibold text-ink-gray-9">
              {{ __('Quy trình tạo bài tự động vừa thực hiện') }}
            </h3>
            <Badge
              v-if="currentBatchId"
              :label="currentBatchId"
              variant="subtle"
              theme="blue"
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-x"
            @click="pipelineSteps = []"
          />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-5 gap-3">
          <div
            v-for="(step, idx) in pipelineSteps"
            :key="idx"
            class="p-3 rounded-lg border border-outline-gray-2 bg-surface-base flex flex-col justify-between"
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="text-base">{{ step.icon }}</span>
              <span class="text-xs font-semibold text-ink-gray-9 truncate">
                {{ step.agent }}
              </span>
            </div>
            <div class="text-[11px] text-ink-gray-5 line-clamp-3">
              {{ step.action }}
            </div>
            <div class="mt-2 flex items-center gap-1 text-[11px] text-green-600 font-medium">
              <LucideCheck class="size-3" />
              <span>Hoàn tất</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Weekly Matrix Schedule (4 Khung giờ chuẩn của tuần) -->
      <div class="rounded-xl border border-outline-gray-1 bg-surface-base p-4 sm:p-5 shadow-xs">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div class="flex items-center gap-2">
            <div class="p-1.5 rounded-lg bg-surface-gray-2 text-ink-gray-9">
              <LucideCalendar class="size-4.5 text-ink-gray-7" />
            </div>
            <div>
              <h2 class="text-sm sm:text-base font-semibold text-ink-gray-9 leading-tight">
                {{ __('Lịch phát sóng tuần chuẩn (EduFlow Autopilot Matrix)') }}
              </h2>
              <div class="text-xs text-ink-gray-5 mt-0.5">
                {{ __('4 bài viết vàng / tuần: Thứ 2, Thứ 4, Thứ 6 & Chủ Nhật') }}
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 flex-wrap">
            <Button
              variant="subtle"
              size="sm"
              :iconLeft="LucideSend"
              :loading="publishingScheduled"
              @click="publishDuePosts"
            >
              {{ __('Đăng bài đến hạn') }}
            </Button>

            <Button
              variant="subtle"
              size="sm"
              :iconLeft="LucideUndo2"
              @click="showRollbackModal = true"
            >
              {{ __('Làm lại cả tuần') }}
            </Button>

            <Button
              variant="subtle"
              size="sm"
              :iconLeft="LucideCheckCheck"
              :loading="approvingBatch"
              @click="approveCurrentBatch"
            >
              {{ __('Duyệt tất cả tuần này') }}
            </Button>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            v-for="slot in weeklyMatrix"
            :key="slot.day_of_week"
            class="rounded-lg border p-3 flex flex-col justify-between transition-all duration-200"
            :class="getSlotCardClass(slot)"
          >
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs font-bold text-ink-gray-8 uppercase tracking-wide">
                  {{ slot.day_of_week }}
                </span>
                <span class="text-xs font-medium text-ink-gray-5 flex items-center gap-1">
                  <LucideClock class="size-3" />
                  {{ slot.time.substring(0, 5) }}
                </span>
              </div>
              <div v-if="getSlotPost(slot)?.course" class="flex items-center gap-1.5 mb-2">
                <span class="text-xs px-2 py-0.5 rounded-full font-semibold" :class="getCourseBadgeClass(getSlotPost(slot).course)">
                  {{ getSlotPost(slot).course }}
                </span>
              </div>
              <img
                v-if="getSlotPost(slot)?.image"
                :src="getSlotPost(slot).image"
                :alt="getSlotPost(slot).title"
                class="w-full h-28 object-cover object-top rounded-md border border-outline-gray-1 mb-2"
              />
              <div class="text-xs font-medium text-ink-gray-8 line-clamp-2">
                {{ getSlotPost(slot)?.title || __('Chưa lên kế hoạch') }}
              </div>
              <div v-if="getSlotPost(slot)?.content" class="mt-1 text-[11px] text-ink-gray-6 line-clamp-3 whitespace-pre-line">
                {{ getSlotPost(slot).content }}
              </div>
              <div v-else-if="getSlotPost(slot)" class="mt-1 text-[11px] text-ink-gray-4 italic">
                {{ __('Chưa có nội dung') }}
              </div>
              <div v-if="getSlotPost(slot)?.plan_reason" class="mt-1 text-[11px] text-ink-gray-5 line-clamp-2" :title="getSlotPost(slot).plan_reason">
                {{ __('Vì sao') }}: {{ getSlotPost(slot).plan_reason }}
              </div>
              <div v-if="getSlotPost(slot)?.content_warning" class="mt-1 text-[11px] text-ink-amber-6 line-clamp-2" :title="getSlotPost(slot).content_warning">
                ⚠ {{ getSlotPost(slot).content_warning }}
              </div>
            </div>

            <div class="mt-3 pt-2 border-t border-outline-gray-1 flex items-center justify-between">
              <template v-if="getSlotPost(slot)">
                <Badge
                  :label="getStatusLabel(getSlotPost(slot).status)"
                  :theme="getStatusTheme(getSlotPost(slot).status)"
                  variant="subtle"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  :label="__('Chi tiết')"
                  @click="openEditModal(getSlotPost(slot))"
                />
              </template>
              <template v-else>
                <span class="text-[11px] text-ink-gray-4 italic">Chưa có bài</span>
                <Button
                  variant="subtle"
                  size="sm"
                  :label="__('+ Tạo bài')"
                  @click="openCreateModalForSlot(slot)"
                />
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Filter Tabs and Stats Bar -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-outline-gray-1">
        <div class="flex items-center gap-1 overflow-x-auto py-1">
          <button
            v-for="tab in filterTabs"
            :key="tab.key"
            class="px-3 py-1.5 text-xs font-medium rounded-lg transition-colors whitespace-nowrap flex items-center gap-1.5"
            :class="activeFilter === tab.key ? 'bg-surface-gray-3 text-ink-gray-9 font-semibold' : 'text-ink-gray-6 hover:bg-surface-gray-2'"
            @click="activeFilter = tab.key"
          >
            <span>{{ tab.label }}</span>
            <span
              class="px-1.5 py-0.2 rounded-full text-[10px]"
              :class="activeFilter === tab.key ? 'bg-surface-base text-ink-gray-9' : 'bg-surface-gray-2 text-ink-gray-5'"
            >
              {{ getCountForFilter(tab.key) }}
            </span>
          </button>
        </div>

        <div class="flex items-center gap-3 text-xs text-ink-gray-5">
          <span>Tổng số: <strong class="text-ink-gray-9">{{ posts.length }}</strong> bài</span>
          <span>•</span>
          <span class="text-amber-600">Chờ duyệt: <strong>{{ pendingCount }}</strong></span>
          <span>•</span>
          <span class="text-blue-600">Đã lên lịch: <strong>{{ scheduledCount }}</strong></span>
          <span>•</span>
          <span class="text-green-600">Đã đăng: <strong>{{ postedCount }}</strong></span>
        </div>
      </div>

      <!-- Empty State -->
      <div
        v-if="!filteredPosts.length && !loading"
        class="py-16 text-center rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1"
      >
        <MegaphoneIcon class="size-10 mx-auto text-ink-gray-4 mb-3" />
        <h3 class="text-base font-semibold text-ink-gray-8">
          {{ activeFilter === 'all' ? __('Chưa có bài đăng Facebook nào') : __('Không có bài viết trong bộ lọc này') }}
        </h3>
        <p class="text-xs text-ink-gray-5 max-w-sm mx-auto mt-1 mb-4">
          {{ __('Bấm nút Lên kế hoạch tuần để tự động tạo 4 bài viết theo ma trận tuyển sinh chuẩn.') }}
        </p>
        <Button
          variant="solid"
          :iconLeft="LucideCalendarPlus"
          @click="showGenerateModal = true"
        >
          {{ __('Lên kế hoạch tuần ngay') }}
        </Button>
      </div>

      <!-- Posts Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="post in filteredPosts"
          :key="post.name"
          class="rounded-xl border border-outline-gray-2 bg-surface-base p-4 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow duration-200"
        >
          <div>
            <!-- Top Card Header: Day, Course, Status -->
            <div class="flex items-center justify-between gap-2 mb-2">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span
                  v-if="post.day_of_week"
                  class="text-[11px] font-bold px-2 py-0.5 rounded bg-surface-gray-2 text-ink-gray-8"
                >
                  {{ post.day_of_week }}
                </span>
                <span
                  class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                  :class="getCourseBadgeClass(post.course)"
                >
                  {{ post.course }}
                </span>
              </div>
              <Badge
                :label="getStatusLabel(post.status)"
                :theme="getStatusTheme(post.status)"
                variant="subtle"
              />
            </div>

            <!-- Post Title -->
            <h3 class="text-sm font-semibold text-ink-gray-9 leading-snug line-clamp-2 mb-1.5">
              {{ post.title }}
            </h3>

            <!-- Schedule info & Batch tag -->
            <div class="flex items-center gap-3 text-xs text-ink-gray-5 mb-2.5 flex-wrap">
              <span v-if="post.scheduled_time" class="flex items-center gap-1">
                <LucideClock class="size-3 text-ink-gray-4" />
                {{ formatDateTime(post.scheduled_time) }}
              </span>
              <span v-if="post.batch_id" class="px-1.5 py-0.2 rounded text-[10px] bg-surface-gray-2 text-ink-gray-6 font-mono">
                {{ post.batch_id }}
              </span>
            </div>

            <!-- Boss Directive tag (if set) -->
            <div
              v-if="post.boss_directive"
              class="mb-2.5 p-2 rounded-lg bg-surface-gray-2 text-[11px] text-ink-gray-7 italic line-clamp-2"
            >
              <strong>Định hướng:</strong> "{{ post.boss_directive }}"
            </div>

            <!-- Content preview -->
            <div class="text-xs text-ink-gray-6 line-clamp-4 whitespace-pre-line mb-3 font-sans">
              {{ post.content || 'Chưa có nội dung...' }}
            </div>

            <!-- Image thumbnail if attached -->
            <div
              v-if="post.image"
              class="mb-3 rounded-lg overflow-hidden border border-outline-gray-1 bg-surface-gray-1 max-h-36 flex items-center justify-center cursor-pointer"
              @click="openImagePreview(post.image)"
            >
              <img :src="post.image" class="w-full h-full object-cover" alt="Banner bài viết" />
            </div>

            <!-- Facebook Post link if posted -->
            <div
              v-if="post.fb_post_url"
              class="mb-3 flex items-center gap-1 text-xs text-blue-600 hover:underline"
            >
              <LucideExternalLink class="size-3" />
              <a :href="post.fb_post_url" target="_blank" rel="noopener noreferrer">
                {{ __('Xem bài viết trên Facebook Fanpage') }}
              </a>
            </div>

            <!-- Facebook Engagement Metrics -->
            <div
              v-if="post.status === 'Posted' || post.likes_count || post.comments_count"
              class="mb-3 p-2 rounded-lg bg-surface-gray-2 border border-outline-gray-2 flex items-center justify-between text-xs text-ink-gray-7 flex-wrap gap-2"
            >
              <div class="flex items-center gap-3">
                <span class="flex items-center gap-1 font-semibold text-blue-600" title="Lượt thích">
                  <LucideThumbsUp class="size-3.5" />
                  {{ post.likes_count || 0 }}
                </span>
                <span class="flex items-center gap-1 font-semibold text-amber-600" title="Bình luận">
                  <LucideMessageSquare class="size-3.5" />
                  {{ post.comments_count || 0 }}
                </span>
                <span v-if="post.leads_count" class="flex items-center gap-1 font-semibold text-emerald-600" title="Khách tiềm năng (Leads)">
                  <LucideSparkles class="size-3.5" />
                  {{ post.leads_count }} leads
                </span>
              </div>
              <span
                v-if="post.ads_recommendation === 'Recommended'"
                class="text-[10px] font-semibold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded"
              >
                Đề xuất Ads
              </span>
            </div>

            <!-- Error message if failed -->
            <div
              v-if="post.error_message"
              class="mb-3 p-2 rounded-lg bg-red-50 text-[11px] text-red-700 font-mono"
            >
              ⚠️ {{ post.error_message }}
            </div>
          </div>

          <!-- Card Actions Footer -->
          <div class="pt-3 border-t border-outline-gray-1 flex items-center justify-between gap-1 flex-wrap">
            <div class="flex items-center gap-1 flex-wrap">
              <!-- Approve button if Pending -->
              <Button
                v-if="post.status === 'Pending Approval'"
                variant="solid"
                size="sm"
                :iconLeft="LucideCheck"
                @click="approveSinglePost(post)"
              >
                {{ __('Duyệt bài') }}
              </Button>

              <!-- Recall button if Scheduled -->
              <Button
                v-if="post.status === 'Scheduled'"
                variant="subtle"
                size="sm"
                :iconLeft="LucideUndo2"
                @click="recallSinglePost(post)"
              >
                {{ __('Thu hồi lịch') }}
              </Button>

              <!-- Post now button for Draft, Pending, Scheduled -->
              <Button
                v-if="['Pending Approval', 'Scheduled', 'Draft', 'Failed'].includes(post.status)"
                variant="ghost"
                size="sm"
                :iconLeft="LucideSend"
                @click="postNow(post)"
              >
                {{ __('Đăng ngay') }}
              </Button>

              <!-- Sync Comments and Analytics buttons if Posted -->
              <template v-if="post.status === 'Posted'">
                <Button
                  variant="subtle"
                  size="sm"
                  :iconLeft="LucideMessageSquare"
                  :loading="syncingCommentsMap[post.name]"
                  :title="__('Đồng bộ bình luận từ Facebook Fanpage')"
                  @click="syncPostComments(post)"
                >
                  {{ __('Đồng bộ BL') }}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  :iconLeft="LucideBarChart2"
                  :loading="syncingAnalyticsMap[post.name]"
                  :title="__('Cập nhật số liệu tương tác')"
                  @click="syncPostAnalytics(post)"
                >
                  <span class="hidden sm:inline">{{ __('Số liệu') }}</span>
                </Button>
              </template>
            </div>

            <div class="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                :iconLeft="LucideEdit"
                @click="openEditModal(post)"
              />
              <Button
                variant="ghost"
                size="sm"
                class="!text-ink-red-6 hover:!bg-surface-red-2"
                :iconLeft="LucideTrash2"
                @click="deletePost(post)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- MODAL 1: LÊN KẾ HOẠCH TUẦN (AUTOPILOT MULTI-AGENT) -->
    <Dialog v-model:open="showGenerateModal" :size="'lg'">
      <template #body>
        <div class="bg-surface-elevation-1 px-5 py-5 sm:p-6">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="p-2 rounded-lg bg-surface-gray-2 text-ink-gray-9">
                <LucideCalendar class="size-5" />
              </div>
              <div>
                <h3 class="text-base font-semibold text-ink-gray-9">
                  {{ __('Lên Kế Hoạch Bài Đăng Tuần') }}
                </h3>
                <p class="text-xs text-ink-gray-5">
                  {{ __('Tự động tạo 4 bài viết theo ma trận tuyển sinh chuẩn') }}
                </p>
              </div>
            </div>
            <Button variant="ghost" icon="lucide-x" @click="showGenerateModal = false" />
          </div>

          <div class="space-y-4 text-xs">
            <div>
              <label class="block font-medium text-ink-gray-8 mb-1.5">
                {{ __('Định hướng tuần này (Tùy chọn)') }}
              </label>
              <textarea
                v-model="generateForm.boss_directive"
                rows="3"
                class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2.5 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                :placeholder="__('Ví dụ: Chiến dịch tuyển sinh tháng 10 - Giảm 30% học phí khóa bơi cho bé, tặng 1 buổi học thử Tiếng Anh cho phụ huynh đăng ký sớm...')"
              />
              <p class="text-[11px] text-ink-gray-5 mt-1">
                {{ __('Nếu để trống, hệ thống sẽ sử dụng chiến lược mặc định: Tuyển sinh đa kênh các khóa học mũi nhọn.') }}
              </p>
            </div>

            <div class="rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-7 space-y-1">
              <div class="font-semibold text-ink-gray-9 mb-1">
                {{ __('Ma trận 4 khung giờ phát sóng:') }}
              </div>
              <div>• <strong>Thứ Hai (08:30):</strong> Tiếng Anh giao tiếp (Storytelling)</div>
              <div>• <strong>Thứ Tư (11:30):</strong> Toán tư duy (Educational Insight)</div>
              <div>• <strong>Thứ Sáu (19:30):</strong> Bơi lội trẻ em (FOMO Offer / Giảm giá)</div>
              <div>• <strong>Chủ Nhật (09:00):</strong> Tổng kết & Học bổng EduFlow (Humor / Community)</div>
            </div>
          </div>

          <div class="mt-6 flex items-center justify-end gap-2">
            <Button
              variant="subtle"
              :label="__('Hủy')"
              @click="showGenerateModal = false"
            />
            <Button
              variant="solid"
              :label="__('Bắt đầu lên lịch tuần')"
              :iconLeft="LucideCalendarPlus"
              :loading="generatingBatch"
              @click="handleGenerateWeeklyBatch"
            />
          </div>
        </div>
      </template>
    </Dialog>

    <!-- MODAL 2: LÀM LẠI CẢ TUẦN (ROLLBACK & REGENERATE) -->
    <Dialog v-model:open="showRollbackModal" :size="'lg'">
      <template #body>
        <div class="bg-surface-elevation-1 px-5 py-5 sm:p-6">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="p-2 rounded-lg bg-amber-100 text-amber-700">
                <LucideUndo2 class="size-5" />
              </div>
              <div>
                <h3 class="text-base font-semibold text-ink-gray-9">
                  {{ __('Làm Lại Kế Hoạch Tuần') }}
                </h3>
                <p class="text-xs text-ink-gray-5">
                  {{ __('Thu hồi các bài chưa đăng tuần này và tạo lại đợt bài mới') }}
                </p>
              </div>
            </div>
            <Button variant="ghost" icon="lucide-x" @click="showRollbackModal = false" />
          </div>

          <div class="space-y-4 text-xs">
            <p class="text-ink-gray-7">
              {{ __('Hệ thống sẽ chuyển tất cả các bài Chờ duyệt hoặc Đã lên lịch của tuần sang trạng thái Hủy (Cancelled), sau đó chạy lại Đa Agent để tạo mới 4 bài theo chỉ đạo mới.') }}
            </p>

            <div>
              <label class="block font-medium text-ink-gray-8 mb-1.5">
                {{ __('Chỉ đạo điều chỉnh mới (Tùy chọn)') }}
              </label>
              <textarea
                v-model="rollbackForm.new_directive"
                rows="3"
                class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2.5 text-xs focus:ring-1 focus:ring-amber-500 focus:outline-none"
                :placeholder="__('Ví dụ: Đổi chủ đề tuần này sang Tuần lễ vàng học bơi sinh tồn...')"
              />
            </div>
          </div>

          <div class="mt-6 flex items-center justify-end gap-2">
            <Button
              variant="subtle"
              :label="__('Hủy')"
              @click="showRollbackModal = false"
            />
            <Button
              variant="solid"
              class="!bg-amber-600 hover:!bg-amber-700"
              :label="__('Xác nhận Làm lại cả tuần')"
              :loading="rollingBackBatch"
              @click="handleRollbackWeeklyBatch"
            />
          </div>
        </div>
      </template>
    </Dialog>

    <!-- MODAL 3: XEM & SỬA BÀI VIẾT (EDIT & AI REWRITE & COMMENTS) -->
    <Dialog v-model:open="showEditModal" :size="'4xl'">
      <template #body>
        <div class="bg-surface-elevation-1 flex flex-col max-h-[85vh] overflow-hidden rounded-xl" v-if="editingPost">
          <!-- Fixed Top Header -->
          <div class="px-5 pt-4 pb-3 border-b border-outline-gray-2 shrink-0 bg-surface-elevation-1">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <Badge
                  :label="getStatusLabel(editingPost.status)"
                  :theme="getStatusTheme(editingPost.status)"
                  variant="subtle"
                />
                <h3 class="text-base font-semibold text-ink-gray-9 truncate max-w-md">
                  #{{ editingPost.name }} - {{ editingPost.title }}
                </h3>
              </div>
              <div class="flex items-center gap-2">
                <a
                  v-if="editingPost.fb_post_url"
                  :href="editingPost.fb_post_url"
                  target="_blank"
                  class="text-xs text-blue-500 hover:underline flex items-center gap-1 font-medium"
                >
                  <LucideExternalLink class="size-3" />
                  {{ __('Facebook') }}
                </a>
                <a
                  :href="'/app/facebook-post/' + editingPost.name"
                  target="_blank"
                  class="text-xs text-ink-gray-5 hover:text-ink-gray-8 flex items-center gap-1 font-medium"
                >
                  <LucideExternalLink class="size-3" />
                  Desk
                </a>
                <Button variant="ghost" icon="lucide-x" @click="showEditModal = false" />
              </div>
            </div>

            <!-- Navigation Tabs -->
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
                :class="activeModalTab === 'content' ? 'bg-surface-gray-3 text-ink-gray-9 shadow-xs' : 'text-ink-gray-6 hover:bg-surface-gray-2'"
                @click="activeModalTab = 'content'"
              >
                <LucideEdit class="size-3.5" />
                <span>{{ __('Nội dung & Thiết lập') }}</span>
              </button>
              <button
                type="button"
                class="px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
                :class="activeModalTab === 'comments' ? 'bg-surface-gray-3 text-ink-gray-9 shadow-xs' : 'text-ink-gray-6 hover:bg-surface-gray-2'"
                @click="activeModalTab = 'comments'"
              >
                <LucideMessageSquare class="size-3.5" />
                <span>{{ __('Bình luận Facebook') }}</span>
                <span
                  class="px-1.5 py-0.2 rounded-full text-[10px]"
                  :class="activeModalTab === 'comments' ? 'bg-surface-base text-ink-gray-9 font-bold' : 'bg-surface-gray-2 text-ink-gray-6'"
                >
                  {{ editingPost.comments?.length || editingPost.comments_count || 0 }}
                </span>
              </button>
              <button
                v-if="editingPost.status === 'Posted' || editingPost.fb_post_id"
                type="button"
                class="px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
                :class="activeModalTab === 'analytics' ? 'bg-surface-gray-3 text-ink-gray-9 shadow-xs' : 'text-ink-gray-6 hover:bg-surface-gray-2'"
                @click="activeModalTab = 'analytics'"
              >
                <LucideBarChart2 class="size-3.5" />
                <span>{{ __('Số liệu & Meta Ads') }}</span>
              </button>
            </div>
          </div>

          <!-- Scrollable Middle Body -->
          <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            <!-- TAB 1: NỘI DUNG & THIẾT LẬP -->
            <div v-show="activeModalTab === 'content'" class="space-y-4 text-xs">
              <!-- Top Metadata & Scheduling Card -->
              <div class="p-3.5 rounded-xl border border-outline-gray-2 bg-surface-gray-1 space-y-2.5">
                <div>
                  <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Tiêu đề bài viết') }}</label>
                  <input
                    v-model="editingPost.title"
                    type="text"
                    class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                    placeholder="Tiêu đề bài viết..."
                  />
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div>
                    <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Khóa học') }}</label>
                    <select
                      v-model="editingPost.course"
                      class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                    >
                      <option v-for="c in availableCourses" :key="c.name" :value="c.name">
                        {{ c.name }} - {{ c.product_name }}
                      </option>
                    </select>
                  </div>

                  <div>
                    <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Thứ trong tuần') }}</label>
                    <select
                      v-model="editingPost.day_of_week"
                      class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                    >
                      <option value="Thứ Hai">Thứ Hai</option>
                      <option value="Thứ Ba">Thứ Ba</option>
                      <option value="Thứ Tư">Thứ Tư</option>
                      <option value="Thứ Năm">Thứ Năm</option>
                      <option value="Thứ Sáu">Thứ Sáu</option>
                      <option value="Thứ Bảy">Thứ Bảy</option>
                      <option value="Chủ Nhật">Chủ Nhật</option>
                    </select>
                  </div>

                  <div>
                    <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Thời gian đăng') }}</label>
                    <input
                      v-model="editingPost.scheduled_time"
                      type="text"
                      placeholder="YYYY-MM-DD HH:MM:SS"
                      class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Trạng thái') }}</label>
                    <select
                      v-model="editingPost.status"
                      class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                    >
                      <option value="Draft">Draft (Bản nháp)</option>
                      <option value="Pending Approval">Pending Approval (Chờ duyệt)</option>
                      <option value="Scheduled">Scheduled (Đã lên lịch)</option>
                      <option value="Posted">Posted (Đã đăng)</option>
                      <option value="Failed">Failed (Lỗi)</option>
                      <option value="Cancelled">Cancelled (Đã hủy)</option>
                    </select>
                  </div>
                </div>
              </div>

              <!-- Balanced 2-Column Split: Content & Banner -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Left Column: Caption & AI Feedback Adjustment -->
                <div class="space-y-3 flex flex-col justify-between">
                  <div>
                    <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Nội dung bài viết (Caption)') }}</label>
                    <textarea
                      v-model="editingPost.content"
                      class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-3 text-xs font-sans leading-relaxed focus:ring-1 focus:ring-blue-500 focus:outline-none h-[220px] resize-y"
                      placeholder="Nhập nội dung bài viết..."
                    />
                  </div>

                  <!-- Content Adjustment Panel -->
                  <div class="p-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1 space-y-2">
                    <div class="flex items-center gap-1.5 font-medium text-xs text-ink-gray-7">
                      <LucideEdit class="size-3.5 text-ink-gray-6" />
                      <span>{{ __('Gợi ý điều chỉnh cho AI') }}</span>
                    </div>
                    <input
                      v-model="editingPost.ai_feedback"
                      type="text"
                      class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                      placeholder="Ví dụ: Thêm ưu đãi giảm 500k, viết ngắn gọn hơn..."
                    />
                    <div class="flex items-center gap-2">
                      <Button
                        variant="subtle"
                        size="sm"
                        :iconLeft="LucideRefreshCcw"
                        :loading="rewritingContent"
                        @click="handleAiRewriteContent"
                      >
                        {{ __('Viết lại nội dung') }}
                      </Button>
                      <Button
                        variant="subtle"
                        size="sm"
                        :iconLeft="LucideImage"
                        :loading="generatingBanner"
                        @click="handleAiGenerateBanner"
                      >
                        {{ __('Tạo lại banner') }}
                      </Button>
                    </div>
                  </div>
                </div>

                <!-- Right Column: Banner Display & Actions -->
                <div class="space-y-2 flex flex-col">
                  <div class="flex items-center justify-between">
                    <label class="font-medium text-ink-gray-8">{{ __('Banner bài viết') }}</label>
                    <button
                      v-if="editingPost.image"
                      type="button"
                      class="text-[11px] text-blue-500 hover:underline flex items-center gap-1 font-medium"
                      @click="openImagePreview(editingPost.image)"
                    >
                      <LucideExternalLink class="size-3" />
                      {{ __('Xem kích thước gốc') }}
                    </button>
                  </div>

                  <div
                    class="flex-1 min-h-[300px] rounded-xl overflow-hidden border border-outline-gray-2 bg-surface-gray-2 flex items-center justify-center p-2 cursor-pointer hover:border-blue-400 transition-colors group relative"
                    @click="editingPost.image && openImagePreview(editingPost.image)"
                    :title="editingPost.image ? 'Bấm để xem ảnh phóng to' : ''"
                  >
                    <template v-if="editingPost.image">
                      <img
                        :src="editingPost.image"
                        class="w-full h-auto max-h-[320px] object-contain rounded-lg mx-auto"
                        alt="Banner Facebook"
                      />
                      <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-medium gap-1.5 rounded-xl">
                        <LucideExternalLink class="size-4" />
                        <span>{{ __('Bấm để xem ảnh phóng to') }}</span>
                      </div>
                    </template>
                    <template v-else>
                      <div class="text-center py-12 text-ink-gray-5">
                        <LucideImage class="size-10 mx-auto text-ink-gray-4 mb-2" />
                        <p class="text-xs">{{ __('Chưa có banner đính kèm') }}</p>
                        <Button
                          variant="subtle"
                          size="sm"
                          class="mt-2"
                          :loading="generatingBanner"
                          @click.stop="handleAiGenerateBanner"
                        >
                          {{ __('Tạo banner bằng AI') }}
                        </Button>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <!-- TAB 2: BÌNH LUẬN FACEBOOK -->
            <div v-show="activeModalTab === 'comments'" class="space-y-4">
              <div class="flex items-center justify-between bg-surface-gray-1 p-3 rounded-lg border border-outline-gray-1">
                <div>
                  <h4 class="text-xs font-semibold text-ink-gray-9 flex items-center gap-1.5">
                    <LucideMessageSquare class="size-3.5 text-amber-500" />
                    {{ __('Bình luận từ Facebook Fanpage') }} ({{ editingPost.comments?.length || 0 }})
                  </h4>
                  <p class="text-[11px] text-ink-gray-5">
                    {{ __('Tự động phân loại: Quan tâm khóa học, Hỏi học phí / lịch, Tích cực, Spam / Khác') }}
                  </p>
                </div>
                <Button
                  variant="solid"
                  size="sm"
                  :iconLeft="LucideRefreshCcw"
                  :loading="syncingCommentsMap[editingPost.name]"
                  @click="syncPostComments(editingPost)"
                >
                  {{ __('Đồng bộ bình luận từ Facebook') }}
                </Button>
              </div>

              <!-- Comments List -->
              <div v-if="editingPost.comments && editingPost.comments.length" class="space-y-2.5 max-h-[55vh] overflow-y-auto pr-1">
                <div
                  v-for="comment in editingPost.comments"
                  :key="comment.name || comment.comment_id"
                  class="p-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1 hover:bg-surface-gray-2 transition-colors flex flex-col gap-1.5 shadow-xs"
                >
                  <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2">
                      <div class="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold uppercase">
                        {{ (comment.from_name || 'K')[0] }}
                      </div>
                      <span class="text-xs font-semibold text-ink-gray-9">{{ comment.from_name || 'Khách Facebook' }}</span>
                      <span v-if="comment.comment_time" class="text-[11px] text-ink-gray-4">
                        {{ formatDateTime(comment.comment_time) }}
                      </span>
                    </div>
                    <Badge
                      :label="comment.sentiment || 'Chưa phân loại'"
                      :theme="getSentimentTheme(comment.sentiment)"
                      variant="subtle"
                    />
                  </div>
                  <div class="text-xs text-ink-gray-8 pl-8 whitespace-pre-wrap font-sans">
                    {{ comment.comment_message }}
                  </div>
                </div>
              </div>

              <!-- Empty State -->
              <div
                v-else
                class="py-12 text-center rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1"
              >
                <LucideMessageSquare class="size-8 mx-auto text-ink-gray-4 mb-2" />
                <p class="text-xs text-ink-gray-7 font-medium">
                  {{ __('Chưa có bình luận nào được lưu cho bài viết này.') }}
                </p>
                <p class="text-[11px] text-ink-gray-5 mt-0.5 mb-3">
                  {{ __('Bấm nút "Đồng bộ bình luận từ Facebook" để tải toàn bộ phản hồi mới nhất của phụ huynh/học viên.') }}
                </p>
                <Button
                  v-if="editingPost.status === 'Posted'"
                  variant="subtle"
                  size="sm"
                  :iconLeft="LucideRefreshCcw"
                  :loading="syncingCommentsMap[editingPost.name]"
                  @click="syncPostComments(editingPost)"
                >
                  {{ __('Tải bình luận ngay') }}
                </Button>
              </div>
            </div>

            <!-- TAB 3: SỐ LIỆU TƯƠNG TÁC & META ADS -->
            <div v-show="activeModalTab === 'analytics'" class="space-y-4">
              <div class="flex items-center justify-between bg-surface-gray-1 p-3 rounded-lg border border-outline-gray-1">
                <div>
                  <h4 class="text-xs font-semibold text-ink-gray-9">{{ __('Hiệu quả tương tác Facebook Fanpage') }}</h4>
                  <p class="text-[11px] text-ink-gray-5" v-if="editingPost.last_analytics_sync">
                    {{ __('Đồng bộ lần cuối:') }} {{ formatDateTime(editingPost.last_analytics_sync) }}
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <Button
                    variant="subtle"
                    size="sm"
                    :iconLeft="LucideBarChart2"
                    :loading="syncingAnalyticsMap[editingPost.name]"
                    @click="syncPostAnalytics(editingPost)"
                  >
                    {{ __('Cập nhật số liệu') }}
                  </Button>
                  <a
                    v-if="editingPost.fb_post_url"
                    :href="editingPost.fb_post_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center gap-1 text-xs text-blue-500 hover:underline px-2 py-1 font-medium"
                  >
                    <LucideExternalLink class="size-3" />
                    {{ __('Xem trên Facebook') }}
                  </a>
                </div>
              </div>

              <!-- Metric KPI Cards -->
              <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div class="p-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1 text-center">
                  <div class="text-[11px] text-ink-gray-5 flex items-center justify-center gap-1 mb-1">
                    <LucideThumbsUp class="size-3 text-blue-500" />
                    {{ __('Lượt thích') }}
                  </div>
                  <div class="text-lg font-bold text-ink-gray-9">{{ editingPost.likes_count || 0 }}</div>
                </div>
                <div class="p-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1 text-center">
                  <div class="text-[11px] text-ink-gray-5 flex items-center justify-center gap-1 mb-1">
                    <LucideMessageSquare class="size-3 text-amber-500" />
                    {{ __('Bình luận') }}
                  </div>
                  <div class="text-lg font-bold text-ink-gray-9">{{ editingPost.comments_count || 0 }}</div>
                </div>
                <div class="p-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1 text-center">
                  <div class="text-[11px] text-ink-gray-5 flex items-center justify-center gap-1 mb-1">
                    <LucideShare2 class="size-3 text-purple-500" />
                    {{ __('Chia sẻ') }}
                  </div>
                  <div class="text-lg font-bold text-ink-gray-9">{{ editingPost.shares_count || 0 }}</div>
                </div>
                <div class="p-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1 text-center">
                  <div class="text-[11px] text-ink-gray-5 flex items-center justify-center gap-1 mb-1">
                    <LucideUsers class="size-3 text-cyan-500" />
                    {{ __('Tiếp cận') }}
                  </div>
                  <div class="text-lg font-bold text-ink-gray-9">{{ editingPost.reach_count || 0 }}</div>
                </div>
                <div class="p-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1 text-center">
                  <div class="text-[11px] text-ink-gray-5 flex items-center justify-center gap-1 mb-1">
                    <LucideSparkles class="size-3 text-emerald-500" />
                    {{ __('Leads') }}
                  </div>
                  <div class="text-lg font-bold text-emerald-600">{{ editingPost.leads_count || 0 }}</div>
                </div>
              </div>

              <!-- Meta Ads Recommendation card -->
              <div class="p-4 rounded-xl border border-outline-gray-2 bg-surface-gray-1 space-y-2">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <LucideSparkles class="size-4 text-ink-gray-7" />
                    <span class="text-xs font-semibold text-ink-gray-9">{{ __('Đánh giá tiềm năng chạy Meta Ads') }}</span>
                  </div>
                  <Badge
                    :label="editingPost.ads_recommendation || 'Not Evaluated'"
                    :theme="editingPost.ads_recommendation === 'Recommended' ? 'green' : (editingPost.ads_recommendation === 'Review' ? 'amber' : 'gray')"
                    variant="subtle"
                  />
                </div>
                <p class="text-xs text-ink-gray-6">
                  <span v-if="editingPost.ads_recommendation === 'Recommended'">
                    🎉 <strong>Khuyên dùng:</strong> Bài viết đạt tương tác tự nhiên tốt và có khách hàng quan tâm. Nên phân bổ ngân sách chạy Ads chuyển đổi / tin nhắn để tối ưu chi phí CPL.
                  </span>
                  <span v-else-if="editingPost.ads_recommendation === 'Review'">
                    ⚖️ <strong>Cân nhắc:</strong> Bài viết bắt đầu có tương tác nhưng cần theo dõi thêm hoặc chỉnh sửa lại lời kêu gọi hành động (CTA) trước khi scale Ads.
                  </span>
                  <span v-else>
                    ℹ️ Chưa đủ dữ liệu tương tác để đánh giá hoặc bài viết có điểm tương tác thấp. Nên kiểm tra nội dung và giờ đăng.
                  </span>
                </p>
              </div>
            </div>
          </div>

          <!-- Fixed Bottom Footer -->
          <div class="px-5 py-3 border-t border-outline-gray-2 flex items-center justify-between shrink-0 bg-surface-elevation-1">
            <div class="flex items-center gap-2">
              <Button
                v-if="['Pending Approval', 'Scheduled', 'Draft'].includes(editingPost.status)"
                variant="subtle"
                :iconLeft="LucideSend"
                @click="postNow(editingPost)"
              >
                {{ __('Đăng ngay lên Fanpage') }}
              </Button>
            </div>
            <div class="flex items-center gap-2">
              <Button
                variant="subtle"
                :label="__('Đóng')"
                @click="showEditModal = false"
              />
              <Button
                v-if="activeModalTab === 'content'"
                variant="solid"
                :label="__('Lưu thay đổi')"
                :loading="savingPost"
                @click="savePostChanges"
              />
            </div>
          </div>
        </div>
      </template>
    </Dialog>

    <!-- MODAL 4: TẠO BÀI VIẾT MỚI (CREATE CUSTOM POST) -->
    <Dialog v-model:open="showCreateModal" :size="'lg'">
      <template #body>
        <div class="bg-surface-elevation-1 px-5 py-5 sm:p-6">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="p-2 rounded-lg bg-surface-gray-2 text-ink-gray-9">
                <LucidePlus class="size-5" />
              </div>
              <div>
                <h3 class="text-base font-semibold text-ink-gray-9">
                  {{ __('Tạo Bài Viết Mới') }}
                </h3>
                <p class="text-xs text-ink-gray-5">
                  {{ __('Soạn thảo hoặc tạo tự động theo khóa học') }}
                </p>
              </div>
            </div>
            <Button variant="ghost" icon="lucide-x" @click="showCreateModal = false" />
          </div>

          <div class="space-y-3 text-xs">
            <div>
              <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Tiêu đề') }} *</label>
              <input
                v-model="createForm.title"
                type="text"
                class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                placeholder="Ví dụ: Khai giảng lớp Tiếng Anh tháng 10..."
              />
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Khóa học') }} *</label>
                <select
                  v-model="createForm.course"
                  class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                >
                  <option v-for="c in availableCourses" :key="c.name" :value="c.name">
                    {{ c.name }} - {{ c.product_name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Thứ trong tuần') }}</label>
                <select
                  v-model="createForm.day_of_week"
                  class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="Thứ Hai">Thứ Hai</option>
                  <option value="Thứ Ba">Thứ Ba</option>
                  <option value="Thứ Tư">Thứ Tư</option>
                  <option value="Thứ Năm">Thứ Năm</option>
                  <option value="Thứ Sáu">Thứ Sáu</option>
                  <option value="Thứ Bảy">Thứ Bảy</option>
                  <option value="Chủ Nhật">Chủ Nhật</option>
                </select>
              </div>
            </div>

            <div>
              <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Lịch hẹn đăng (Tùy chọn)') }}</label>
              <input
                v-model="createForm.scheduled_time"
                type="text"
                placeholder="YYYY-MM-DD HH:MM:SS"
                class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Nội dung bài viết') }}</label>
              <textarea
                v-model="createForm.content"
                rows="6"
                class="w-full rounded-lg border border-outline-gray-2 bg-surface-gray-2 text-ink-gray-9 placeholder:text-ink-gray-4 p-2.5 text-xs leading-relaxed focus:ring-1 focus:ring-blue-500 focus:outline-none"
                placeholder="Nhập nội dung bài viết..."
              />
            </div>
          </div>

          <div class="mt-6 flex items-center justify-end gap-2">
            <Button
              variant="subtle"
              :label="__('Hủy')"
              @click="showCreateModal = false"
            />
            <Button
              variant="solid"
              :label="__('Tạo bài viết')"
              :loading="creatingPost"
              @click="handleCreatePost"
            />
          </div>
        </div>
      </template>
    </Dialog>

    <!-- IMAGE PREVIEW MODAL -->
    <Dialog v-model:open="showImageModal" :size="'4xl'">
      <template #body>
        <div class="p-4 bg-surface-elevation-1 flex flex-col items-center">
          <div class="w-full flex justify-end mb-2">
            <Button variant="ghost" icon="lucide-x" @click="showImageModal = false" />
          </div>
          <img :src="previewImageUrl" class="max-h-[80vh] max-w-full rounded-lg shadow-lg object-contain" />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { call, Button, Badge, Dialog, toast, Dropdown } from 'frappe-ui'
import LayoutHeader from '@/components/LayoutHeader.vue'

// Lucide Icons
import MegaphoneIcon from '~icons/lucide/megaphone'
import LucideCalendarPlus from '~icons/lucide/calendar-plus'
import LucideImage from '~icons/lucide/image'
import LucideRefreshCcw from '~icons/lucide/refresh-ccw'
import LucideCalendar from '~icons/lucide/calendar'
import LucideClock from '~icons/lucide/clock'
import LucideCheck from '~icons/lucide/check'
import LucideCheckCheck from '~icons/lucide/check-check'
import LucideUndo2 from '~icons/lucide/undo-2'
import LucideSend from '~icons/lucide/send'
import LucidePlus from '~icons/lucide/plus'
import LucideEdit from '~icons/lucide/edit'
import LucideTrash2 from '~icons/lucide/trash-2'
import LucideExternalLink from '~icons/lucide/external-link'
import LucideMessageSquare from '~icons/lucide/message-square'
import LucideBarChart2 from '~icons/lucide/bar-chart-2'
import LucideThumbsUp from '~icons/lucide/thumbs-up'
import LucideShare2 from '~icons/lucide/share-2'
import LucideUsers from '~icons/lucide/users'
import LucideSparkles from '~icons/lucide/sparkles'

// State
const posts = ref([])
const loading = ref(false)
const availableCourses = ref([
  { name: 'DH-PTS', product_name: 'Photoshop cơ bản' },
  { name: 'TE-ROBO', product_name: 'Robotics STEM' },
  { name: 'VP-EXCEL', product_name: 'Tin học văn phòng & Excel' },
  { name: 'LT-PY', product_name: 'Python cơ bản' },
  { name: 'AI-BASIC', product_name: 'AI cho người mới bắt đầu' },
  { name: 'MKT-FB', product_name: 'Quảng cáo Facebook Ads' },
  { name: 'Chung', product_name: 'Tuyển sinh chung EduFlow' },
])
const weeklyMatrix = ref([
  // Courses are chosen each week from CRM data (marketing_plan.plan_week, D-123); a slot is day, time and angle.
  { day: 0, day_of_week: 'Thứ Hai', time: '08:30:00' },
  { day: 2, day_of_week: 'Thứ Tư', time: '11:30:00' },
  { day: 4, day_of_week: 'Thứ Sáu', time: '19:30:00' },
  { day: 6, day_of_week: 'Chủ Nhật', time: '09:00:00' },
])

const activeFilter = ref('all')
const filterTabs = [
  { key: 'all', label: 'Tất cả' },
  { key: 'Pending Approval', label: 'Chờ duyệt' },
  { key: 'Scheduled', label: 'Đã lên lịch' },
  { key: 'Posted', label: 'Đã đăng' },
  { key: 'Draft', label: 'Bản nháp' },
  { key: 'Cancelled', label: 'Đã hủy / Lỗi' },
]

// Pipeline and Batch state
const pipelineSteps = ref([])
const currentBatchId = ref('')

// Action Loading states
const generatingBatch = ref(false)
const approvingBatch = ref(false)
const rollingBackBatch = ref(false)
const publishingScheduled = ref(false)
const savingPost = ref(false)
const creatingPost = ref(false)
const rewritingContent = ref(false)
const generatingBanner = ref(false)
const syncingCommentsMap = ref({})
const syncingAnalyticsMap = ref({})

const batchActions = computed(() => [
  {
    label: __('Đăng bài đến hạn'),
    icon: 'send',
    onClick: publishDuePosts,
  },
  {
    label: __('Duyệt tất cả tuần này'),
    icon: 'check-check',
    onClick: approveCurrentBatch,
  },
  {
    label: __('Làm lại cả tuần'),
    icon: 'rotate-ccw',
    onClick: () => {
      showRollbackModal.value = true
    },
  },
])

// Modals
const showGenerateModal = ref(false)
const showRollbackModal = ref(false)
const showEditModal = ref(false)
const showCreateModal = ref(false)
const showImageModal = ref(false)
const previewImageUrl = ref('')
const activeModalTab = ref('content') // 'content', 'comments', 'analytics'

// Form states
const generateForm = ref({ boss_directive: '' })
const rollbackForm = ref({ new_directive: '' })
const editingPost = ref(null)
const createForm = ref({
  title: '',
  course: 'DH-PTS',
  day_of_week: 'Thứ Hai',
  scheduled_time: '',
  content: '',
})

// Counts
const pendingCount = computed(() => posts.value.filter(p => p.status === 'Pending Approval').length)
const scheduledCount = computed(() => posts.value.filter(p => p.status === 'Scheduled').length)
const postedCount = computed(() => posts.value.filter(p => p.status === 'Posted').length)

const filteredPosts = computed(() => {
  if (activeFilter.value === 'all') return posts.value
  if (activeFilter.value === 'Cancelled') {
    return posts.value.filter(p => ['Cancelled', 'Failed'].includes(p.status))
  }
  return posts.value.filter(p => p.status === activeFilter.value)
})

function getCountForFilter(key) {
  if (key === 'all') return posts.value.length
  if (key === 'Cancelled') {
    return posts.value.filter(p => ['Cancelled', 'Failed'].includes(p.status)).length
  }
  return posts.value.filter(p => p.status === key).length
}

// Fetch posts list & courses
async function fetchCourses() {
  try {
    const res = await call('frappe.client.get_list', {
      doctype: 'CRM Product',
      fields: ['name', 'product_name'],
      limit_page_length: 60,
    })
    if (res && res.length) {
      const map = new Map()
      res.forEach(item => map.set(item.name, item))
      availableCourses.value.forEach(item => {
        if (!map.has(item.name)) map.set(item.name, item)
      })
      availableCourses.value = Array.from(map.values())
    }
  } catch (error) {
    console.error('Lỗi tải danh mục khóa học:', error)
  }
}

async function fetchPosts() {
  loading.value = true
  try {
    const res = await call('frappe.client.get_list', {
      doctype: 'Facebook Post',
      fields: [
        'name',
        'title',
        'course',
        'status',
        'day_of_week',
        'scheduled_time',
        'batch_id',
        'boss_directive',
        'ai_feedback',
        'posted_at',
        'fb_post_id',
        'fb_post_url',
        'content',
        'image',
        'likes_count',
        'comments_count',
        'shares_count',
        'reach_count',
        'leads_count',
        'registrations_count',
        'plan_reason',
        'content_warning',
        'ads_recommendation',
        'last_analytics_sync',
        'error_message',
        'modified',
      ],
      order_by: 'scheduled_time desc, modified desc',
      limit_page_length: 60,
    })
    posts.value = res || []

    // Fetch matrix
    try {
      const matrix = await call('mmm_custom.autopilot.get_weekly_matrix')
      if (matrix && matrix.length) {
        weeklyMatrix.value = matrix
      }
    } catch {
      // fallback matrix already set
    }
  } catch (error) {
    console.error('Lỗi tải bài viết Facebook:', error)
  } finally {
    loading.value = false
  }
}

// Matrix Helpers
function getSlotPost(slot) {
  return posts.value.find(
    p => p.day_of_week === slot.day_of_week && ['Pending Approval', 'Scheduled', 'Posted'].includes(p.status)
  ) || posts.value.find(p => p.day_of_week === slot.day_of_week)
}

function getSlotCardClass(slot) {
  const post = getSlotPost(slot)
  if (!post) return 'border-outline-gray-2 bg-surface-gray-1 opacity-70'
  if (post.status === 'Posted') return 'border-green-200 bg-green-50/20'
  if (post.status === 'Scheduled') return 'border-blue-200 bg-blue-50/20'
  if (post.status === 'Pending Approval') return 'border-amber-200 bg-amber-50/20'
  return 'border-outline-gray-2 bg-surface-base'
}

// Badges & Themes
function getCourseBadgeClass(course) {
  switch (course) {
    case 'DH-PTS':
    case 'DH-PTS-NC':
    case 'DH-AI':
      return 'bg-purple-100 text-purple-800'
    case 'TE-ROBO':
      return 'bg-amber-100 text-amber-800'
    case 'VP-EXCEL':
    case 'KT-EXCEL':
      return 'bg-emerald-100 text-emerald-800'
    case 'LT-PY':
    case 'CNTT-PY':
    case 'LT-WEB':
      return 'bg-blue-100 text-blue-800'
    case 'AI-BASIC':
    case 'AI-N8N':
    case 'AI-VIBE':
      return 'bg-purple-100 text-purple-800'
    case 'MKT-FB':
      return 'bg-teal-100 text-teal-800'
    case 'Tiếng Anh':
      return 'bg-blue-100 text-blue-800'
    case 'Bơi lội':
      return 'bg-teal-100 text-teal-800'
    case 'Toán tư duy':
      return 'bg-purple-100 text-purple-800'
    case 'Chung':
    default:
      return 'bg-orange-100 text-orange-800'
  }
}

function getStatusLabel(status) {
  const map = {
    'Draft': 'Bản nháp',
    'Pending Approval': 'Chờ duyệt',
    'Scheduled': 'Đã lên lịch',
    'Posted': 'Đã đăng',
    'Failed': 'Lỗi đăng',
    'Cancelled': 'Đã hủy',
  }
  return map[status] || status
}

function getStatusTheme(status) {
  switch (status) {
    case 'Pending Approval':
      return 'amber'
    case 'Scheduled':
      return 'blue'
    case 'Posted':
      return 'green'
    case 'Failed':
      return 'red'
    case 'Cancelled':
      return 'gray'
    case 'Draft':
    default:
      return 'gray'
  }
}

function formatDateTime(dtStr) {
  if (!dtStr) return ''
  try {
    const d = new Date(dtStr)
    return d.toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dtStr
  }
}

// Autopilot Action Handlers
async function handleGenerateWeeklyBatch() {
  generatingBatch.value = true
  try {
    const res = await call('mmm_custom.autopilot.generate_weekly_batch', {
      boss_directive: generateForm.value.boss_directive || null,
    })
    if (res.status === 'success') {
      currentBatchId.value = res.batch_id
      pipelineSteps.value = res.pipeline || []
      showGenerateModal.value = false
      generateForm.value.boss_directive = ''
      toast.success ? toast.success(`Đã tạo thành công ${res.count} bài viết cho đợt ${res.batch_id}!`) : toast.info(`Đã tạo thành công ${res.count} bài viết!`)
      await fetchPosts()
    }
  } catch (error) {
    console.error('Lỗi tạo đợt bài tuần:', error)
    toast.error ? toast.error('Không thể tạo đợt bài tuần. Vui lòng thử lại.') : toast.info('Lỗi tạo bài.')
  } finally {
    generatingBatch.value = false
  }
}

async function approveCurrentBatch() {
  approvingBatch.value = true
  try {
    const res = await call('mmm_custom.autopilot.approve_weekly_batch')
    if (res.status === 'success') {
      toast.success ? toast.success(`Đã duyệt ${res.approved_count} bài viết!`) : toast.info(`Đã duyệt ${res.approved_count} bài viết!`)
      await fetchPosts()
    }
  } catch (error) {
    console.error('Lỗi duyệt đợt bài:', error)
  } finally {
    approvingBatch.value = false
  }
}

async function handleRollbackWeeklyBatch() {
  rollingBackBatch.value = true
  try {
    const res = await call('mmm_custom.autopilot.rollback_weekly_batch', {
      new_directive: rollbackForm.value.new_directive || null,
    })
    if (res.status === 'success') {
      pipelineSteps.value = res.pipeline || []
      showRollbackModal.value = false
      rollbackForm.value.new_directive = ''
      toast.success ? toast.success(`Đã thu hồi ${res.cancelled_count} bài cũ và tạo mới thành công!`) : toast.info('Đã làm lại cả tuần thành công!')
      await fetchPosts()
    }
  } catch (error) {
    console.error('Lỗi làm lại cả tuần:', error)
  } finally {
    rollingBackBatch.value = false
  }
}

async function publishDuePosts() {
  publishingScheduled.value = true
  try {
    const res = await call('mmm_custom.autopilot.publish_scheduled_posts')
    if (res.status === 'success') {
      toast.success ? toast.success(`Đã đăng thành công ${res.published} bài viết lên Facebook!`) : toast.info(`Đã đăng ${res.published} bài viết!`)
      await fetchPosts()
    }
  } catch (error) {
    console.error('Lỗi đăng bài:', error)
  } finally {
    publishingScheduled.value = false
  }
}

// Single Post Actions
async function approveSinglePost(post) {
  try {
    await call('frappe.client.set_value', {
      doctype: 'Facebook Post',
      name: post.name,
      fieldname: 'status',
      value: 'Scheduled',
    })
    toast.success ? toast.success(`Đã duyệt bài "${post.title}" sang trạng thái Đã lên lịch!`) : toast.info('Đã duyệt bài!')
    await fetchPosts()
  } catch (error) {
    console.error('Lỗi duyệt bài:', error)
  }
}

async function recallSinglePost(post) {
  try {
    await call('mmm_custom.autopilot.recall_post', {
      post_name: post.name,
    })
    toast.info(`Đã thu hồi lịch bài "${post.title}" về Chờ duyệt!`)
    await fetchPosts()
  } catch (error) {
    console.error('Lỗi thu hồi bài:', error)
  }
}

async function postNow(post) {
  try {
    const res = await call('run_doc_method', {
      dt: 'Facebook Post',
      dn: post.name,
      method: 'post_now',
    })
    toast.success ? toast.success('Đã đăng bài viết thành công lên Facebook Fanpage!') : toast.info('Đã đăng bài viết!')
    await fetchPosts()
    if (showEditModal.value) showEditModal.value = false
  } catch (error) {
    console.error('Lỗi đăng bài ngay:', error)
    await fetchPosts()
  }
}

async function deletePost(post) {
  if (!confirm(`Bạn có chắc chắn muốn xóa bài viết "${post.title}" không?`)) return
  try {
    await call('frappe.client.delete', {
      doctype: 'Facebook Post',
      name: post.name,
    })
    toast.info('Đã xóa bài viết.')
    await fetchPosts()
  } catch (error) {
    console.error('Lỗi xóa bài:', error)
  }
}

// Edit & AI Rewrite Handlers
async function openEditModal(post) {
  editingPost.value = JSON.parse(JSON.stringify(post))
  activeModalTab.value = 'content'
  showEditModal.value = true
  try {
    const fullDoc = await call('frappe.client.get', {
      doctype: 'Facebook Post',
      name: post.name,
    })
    if (fullDoc) {
      editingPost.value = fullDoc
      if (fullDoc.course && !availableCourses.value.find(c => c.name === fullDoc.course)) {
        availableCourses.value.push({ name: fullDoc.course, product_name: fullDoc.course })
      }
    }
  } catch (error) {
    console.error('Lỗi tải chi tiết bài viết:', error)
  }
}

// Sync Comments & Analytics Handlers
async function syncPostComments(post) {
  if (!post || !post.name) return
  syncingCommentsMap.value[post.name] = true
  try {
    const res = await call('mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.sync_post_comments', {
      post_name: post.name,
    })
    if (res && res.status === 'success') {
      toast.success ? toast.success(`Đã đồng bộ ${res.comments_count} bình luận từ Facebook!`) : toast.info(`Đã đồng bộ ${res.comments_count} bình luận!`)
      if (editingPost.value && editingPost.value.name === post.name) {
        editingPost.value.comments = res.comments
        editingPost.value.comments_count = res.comments_count
      }
      const p = posts.value.find(x => x.name === post.name)
      if (p) {
        p.comments_count = res.comments_count
      }
    }
  } catch (error) {
    console.error('Lỗi đồng bộ bình luận:', error)
    toast.error ? toast.error('Lỗi đồng bộ bình luận: ' + (error.message || error)) : null
  } finally {
    syncingCommentsMap.value[post.name] = false
  }
}

async function syncPostAnalytics(post) {
  if (!post || !post.name) return
  syncingAnalyticsMap.value[post.name] = true
  try {
    const res = await call('mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.sync_post_analytics', {
      post_name: post.name,
    })
    if (res && res.status === 'success') {
      toast.success ? toast.success('Đã cập nhật số liệu tương tác từ Facebook!') : toast.info('Đã cập nhật số liệu!')
      if (editingPost.value && editingPost.value.name === post.name) {
        const fullDoc = await call('frappe.client.get', {
          doctype: 'Facebook Post',
          name: post.name,
        })
        if (fullDoc) editingPost.value = fullDoc
      }
      await fetchPosts()
    }
  } catch (error) {
    console.error('Lỗi cập nhật số liệu:', error)
    toast.error ? toast.error('Lỗi cập nhật số liệu: ' + (error.message || error)) : null
  } finally {
    syncingAnalyticsMap.value[post.name] = false
  }
}

function getSentimentTheme(sentiment) {
  switch (sentiment) {
    case 'Quan tâm khóa học':
      return 'blue'
    case 'Hỏi học phí / lịch':
      return 'amber'
    case 'Tích cực':
      return 'green'
    case 'Spam / Khác':
    default:
      return 'gray'
  }
}

async function savePostChanges() {
  if (!editingPost.value) return
  savingPost.value = true
  try {
    await call('frappe.client.set_value', {
      doctype: 'Facebook Post',
      name: editingPost.value.name,
      fieldname: {
        title: editingPost.value.title,
        course: editingPost.value.course,
        day_of_week: editingPost.value.day_of_week,
        scheduled_time: editingPost.value.scheduled_time,
        status: editingPost.value.status,
        content: editingPost.value.content,
        ai_feedback: editingPost.value.ai_feedback,
      },
    })
    toast.success ? toast.success('Đã lưu thay đổi bài viết!') : toast.info('Đã lưu thay đổi!')
    showEditModal.value = false
    await fetchPosts()
  } catch (error) {
    console.error('Lỗi lưu bài viết:', error)
  } finally {
    savingPost.value = false
  }
}

async function handleAiRewriteContent() {
  if (!editingPost.value) return
  rewritingContent.value = true
  try {
    const res = await call('run_doc_method', {
      dt: 'Facebook Post',
      dn: editingPost.value.name,
      method: 'generate_ai_content',
      args: { user_feedback: editingPost.value.ai_feedback || null },
    })
    if (res?.content) {
      editingPost.value.content = res.content
    }
    // Reload doc to ensure all fields are synchronized
    const updated = await call('frappe.client.get', {
      doctype: 'Facebook Post',
      name: editingPost.value.name,
    })
    if (updated?.content) {
      editingPost.value.content = updated.content
    }
    const p = posts.value.find(x => x.name === editingPost.value.name)
    if (p && editingPost.value.content) {
      p.content = editingPost.value.content
    }
    toast.success ? toast.success('AI đã viết lại nội dung thành công!') : toast.info('Đã viết lại nội dung!')
  } catch (error) {
    console.error('Lỗi AI viết lại:', error)
    toast.error ? toast.error('Lỗi khi AI viết lại: ' + (error.message || error)) : null
  } finally {
    rewritingContent.value = false
  }
}

async function handleAiGenerateBanner() {
  if (!editingPost.value) return
  generatingBanner.value = true
  try {
    const res = await call('run_doc_method', {
      dt: 'Facebook Post',
      dn: editingPost.value.name,
      method: 'generate_banner',
      args: { user_feedback: editingPost.value.ai_feedback || null },
    })
    if (res?.image) {
      editingPost.value.image = res.image
    }
    const updated = await call('frappe.client.get', {
      doctype: 'Facebook Post',
      name: editingPost.value.name,
    })
    if (updated?.image) {
      editingPost.value.image = updated.image
    }
    const p = posts.value.find(x => x.name === editingPost.value.name)
    if (p && editingPost.value.image) {
      p.image = editingPost.value.image
    }
    toast.success ? toast.success('AI đã tạo mới Banner chuẩn 1080x1080!') : toast.info('Đã tạo mới Banner!')
  } catch (error) {
    console.error('Lỗi AI tạo banner:', error)
    toast.error ? toast.error('Lỗi khi AI tạo banner: ' + (error.message || error)) : null
  } finally {
    generatingBanner.value = false
  }
}

// Custom Create Post
function openCreateModal() {
  createForm.value = {
    title: '',
    course: availableCourses.value[0]?.name || 'DH-PTS',
    day_of_week: 'Thứ Hai',
    scheduled_time: '',
    content: '',
  }
  showCreateModal.value = true
}

function openCreateModalForSlot(slot) {
  createForm.value = {
    title: slot.default_title || '',
    course: slot.course || '',
    day_of_week: slot.day_of_week,
    scheduled_time: '',
    content: '',
  }
  showCreateModal.value = true
}

async function handleCreatePost() {
  if (!createForm.value.title) {
    alert('Vui lòng nhập tiêu đề bài viết.')
    return
  }
  creatingPost.value = true
  try {
    const res = await call('frappe.client.insert', {
      doc: {
        doctype: 'Facebook Post',
        title: createForm.value.title,
        course: createForm.value.course,
        day_of_week: createForm.value.day_of_week,
        scheduled_time: createForm.value.scheduled_time || null,
        status: 'Draft',
        content: createForm.value.content || '',
      },
    })
    toast.success ? toast.success('Đã tạo bài viết mới!') : toast.info('Đã tạo bài viết!')
    showCreateModal.value = false
    await fetchPosts()
    if (res && res.name) {
      openEditModal(res)
    }
  } catch (error) {
    console.error('Lỗi tạo bài viết mới:', error)
  } finally {
    creatingPost.value = false
  }
}

function openImagePreview(url) {
  previewImageUrl.value = url
  showImageModal.value = true
}

onMounted(() => {
  fetchPosts()
  fetchCourses()
})
</script>
