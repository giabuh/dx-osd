<template>
  <div class="flex flex-col h-full overflow-hidden bg-surface-base">
    <!-- Top Header -->
    <LayoutHeader>
      <template #left-header>
        <div class="flex items-center gap-2">
          <div class="p-1.5 rounded-lg bg-surface-gray-2 text-ink-gray-9">
            <MegaphoneIcon class="size-4.5" />
          </div>
          <div>
            <h1 class="text-lg-semibold text-ink-gray-9 leading-none">
              {{ __('Facebook Marketing') }}
            </h1>
            <p class="text-xs text-ink-gray-5 mt-0.5">
              {{ __('Tự động hóa đăng bài & Quản lý Fanpage bằng Đa Agent Gemini AI') }}
            </p>
          </div>
        </div>
      </template>
      <template #right-header>
        <div class="flex items-center gap-2 flex-wrap">
          <Button
            variant="ghost"
            :iconLeft="LucideRefreshCcw"
            :loading="loading"
            @click="fetchPosts"
          >
            {{ __('Làm mới') }}
          </Button>

          <Button
            variant="subtle"
            :iconLeft="LucideSend"
            :loading="publishingScheduled"
            @click="publishDuePosts"
          >
            {{ __('Đăng bài đến hạn') }}
          </Button>

          <Button
            variant="subtle"
            :iconLeft="LucideUndo2"
            @click="showRollbackModal = true"
          >
            {{ __('Làm lại cả tuần') }}
          </Button>

          <Button
            variant="subtle"
            :iconLeft="LucideCheckCheck"
            :loading="approvingBatch"
            @click="approveCurrentBatch"
          >
            {{ __('Duyệt tất cả tuần này') }}
          </Button>

          <Button
            variant="solid"
            :iconLeft="LucideSparkles"
            @click="showGenerateModal = true"
          >
            {{ __('Lên kế hoạch tuần (Autopilot)') }}
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
            <span class="text-base">🤖</span>
            <h3 class="text-sm font-semibold text-ink-gray-9">
              {{ __('Quy trình Đa Agent tự động hóa vừa thực hiện') }}
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
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-2">
            <LucideCalendar class="size-4 text-ink-gray-7" />
            <h2 class="text-base font-semibold text-ink-gray-9">
              {{ __('Lịch phát sóng tuần chuẩn (EduFlow Autopilot Matrix)') }}
            </h2>
          </div>
          <div class="text-xs text-ink-gray-5">
            {{ __('4 bài viết vàng / tuần: Thứ 2, Thứ 4, Thứ 6 & Chủ Nhật') }}
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
              <div class="flex items-center gap-1.5 mb-2">
                <span class="text-xs px-2 py-0.5 rounded-full font-semibold" :class="getCourseBadgeClass(slot.course)">
                  {{ slot.course }}
                </span>
              </div>
              <div class="text-xs text-ink-gray-7 line-clamp-2">
                {{ getSlotPost(slot)?.title || slot.default_title }}
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
          {{ __('Bấm nút Lên kế hoạch tuần để AI Gemini tự động tạo 4 bài viết theo ma trận tuyển sinh chuẩn.') }}
        </p>
        <Button
          variant="solid"
          :iconLeft="LucideSparkles"
          @click="showGenerateModal = true"
        >
          {{ __('Lên kế hoạch tuần bằng AI ngay') }}
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
              🎯 <strong>Chỉ đạo:</strong> "{{ post.boss_directive }}"
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
            <div class="flex items-center gap-1">
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
              <div class="p-2 rounded-lg bg-blue-100 text-blue-700">
                <LucideSparkles class="size-5" />
              </div>
              <div>
                <h3 class="text-base font-semibold text-ink-gray-9">
                  {{ __('Lên Kế Hoạch Tuần Bằng AI Multi-Agent') }}
                </h3>
                <p class="text-xs text-ink-gray-5">
                  {{ __('Đa Agent Gemini AI tự động tạo 4 bài viết theo ma trận tuyển sinh chuẩn') }}
                </p>
              </div>
            </div>
            <Button variant="ghost" icon="lucide-x" @click="showGenerateModal = false" />
          </div>

          <div class="space-y-4 text-xs">
            <div>
              <label class="block font-medium text-ink-gray-8 mb-1.5">
                {{ __('Chỉ đạo của Sếp (Boss Directive - Tùy chọn)') }}
              </label>
              <textarea
                v-model="generateForm.boss_directive"
                rows="3"
                class="w-full rounded-lg border border-outline-gray-2 p-2.5 text-xs text-ink-gray-9 focus:ring-1 focus:ring-blue-500"
                :placeholder="__('Ví dụ: Chiến dịch tuyển sinh tháng 10 - Giảm 30% học phí khóa bơi cho bé, tặng 1 buổi học thử Tiếng Anh cho phụ huynh đăng ký sớm...')"
              />
              <p class="text-[11px] text-ink-gray-5 mt-1">
                {{ __('Nếu để trống, AI sẽ sử dụng chiến lược mặc định: Tuyển sinh đa kênh các khóa học mũi nhọn.') }}
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
              :label="__('Khởi chạy Đa Agent')"
              :iconLeft="LucideSparkles"
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
                class="w-full rounded-lg border border-outline-gray-2 p-2.5 text-xs text-ink-gray-9 focus:ring-1 focus:ring-amber-500"
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

    <!-- MODAL 3: XEM & SỬA BÀI VIẾT (EDIT & AI REWRITE) -->
    <Dialog v-model:open="showEditModal" :size="'2xl'">
      <template #body>
        <div class="bg-surface-elevation-1 px-5 py-5 sm:p-6" v-if="editingPost">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <Badge
                :label="getStatusLabel(editingPost.status)"
                :theme="getStatusTheme(editingPost.status)"
                variant="subtle"
              />
              <h3 class="text-base font-semibold text-ink-gray-9">
                {{ editingPost.name }} - {{ editingPost.title }}
              </h3>
            </div>
            <div class="flex items-center gap-2">
              <a
                :href="'/app/facebook-post/' + editingPost.name"
                target="_blank"
                class="text-xs text-ink-gray-5 hover:text-ink-gray-8 flex items-center gap-1"
              >
                <LucideExternalLink class="size-3" />
                Mở trong Desk
              </a>
              <Button variant="ghost" icon="lucide-x" @click="showEditModal = false" />
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <!-- Left Column: Properties & Schedule -->
            <div class="space-y-3">
              <div>
                <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Tiêu đề') }}</label>
                <input
                  v-model="editingPost.title"
                  type="text"
                  class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
                />
              </div>

              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Khóa học') }}</label>
                  <select
                    v-model="editingPost.course"
                    class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
                  >
                    <option value="Tiếng Anh">Tiếng Anh</option>
                    <option value="Bơi lội">Bơi lội</option>
                    <option value="Toán tư duy">Toán tư duy</option>
                    <option value="Chung">Chung</option>
                  </select>
                </div>
                <div>
                  <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Thứ trong tuần') }}</label>
                  <select
                    v-model="editingPost.day_of_week"
                    class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
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

              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Thời gian đăng') }}</label>
                  <input
                    v-model="editingPost.scheduled_time"
                    type="text"
                    placeholder="YYYY-MM-DD HH:MM:SS"
                    class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
                  />
                </div>
                <div>
                  <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Trạng thái') }}</label>
                  <select
                    v-model="editingPost.status"
                    class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
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

              <!-- AI Rewrite Panel -->
              <div class="p-3 rounded-lg border border-blue-100 bg-blue-50/50 space-y-2">
                <div class="flex items-center gap-1.5 font-semibold text-blue-900">
                  <LucideSparkles class="size-3.5 text-blue-600" />
                  <span>{{ __('Gợi ý cho AI điều chỉnh lại') }}</span>
                </div>
                <input
                  v-model="editingPost.ai_feedback"
                  type="text"
                  class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs bg-white"
                  placeholder="Ví dụ: Thêm ưu đãi giảm 500k, viết ngắn gọn hơn..."
                />
                <div class="flex items-center gap-2">
                  <Button
                    variant="subtle"
                    size="sm"
                    :loading="rewritingContent"
                    @click="handleAiRewriteContent"
                  >
                    ✍️ AI Viết lại Caption
                  </Button>
                  <Button
                    variant="subtle"
                    size="sm"
                    :loading="generatingBanner"
                    @click="handleAiGenerateBanner"
                  >
                    🎨 AI Tạo lại Banner
                  </Button>
                </div>
              </div>

              <!-- Attached Banner preview -->
              <div v-if="editingPost.image">
                <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Banner đính kèm') }}</label>
                <div class="rounded-lg overflow-hidden border border-outline-gray-1 max-h-40">
                  <img :src="editingPost.image" class="w-full h-full object-cover" />
                </div>
              </div>
            </div>

            <!-- Right Column: Content Caption -->
            <div class="space-y-2 flex flex-col h-full">
              <label class="block font-medium text-ink-gray-8">{{ __('Nội dung bài viết (Caption)') }}</label>
              <textarea
                v-model="editingPost.content"
                rows="14"
                class="flex-1 w-full rounded-lg border border-outline-gray-2 p-2.5 text-xs text-ink-gray-9 font-sans leading-relaxed resize-none focus:ring-1 focus:ring-blue-500"
                placeholder="Nhập nội dung bài viết..."
              />
            </div>
          </div>

          <div class="mt-6 flex items-center justify-between border-t border-outline-gray-1 pt-3">
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
              <div class="p-2 rounded-lg bg-green-100 text-green-700">
                <LucidePlus class="size-5" />
              </div>
              <div>
                <h3 class="text-base font-semibold text-ink-gray-9">
                  {{ __('Tạo Bài Viết Facebook Mới') }}
                </h3>
                <p class="text-xs text-ink-gray-5">
                  {{ __('Soạn bài hoặc để AI gợi ý nội dung') }}
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
                class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
                placeholder="Ví dụ: Khai giảng lớp Tiếng Anh tháng 10..."
              />
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Khóa học') }} *</label>
                <select
                  v-model="createForm.course"
                  class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
                >
                  <option value="Tiếng Anh">Tiếng Anh</option>
                  <option value="Bơi lội">Bơi lội</option>
                  <option value="Toán tư duy">Toán tư duy</option>
                  <option value="Chung">Chung</option>
                </select>
              </div>
              <div>
                <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Thứ trong tuần') }}</label>
                <select
                  v-model="createForm.day_of_week"
                  class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
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
                class="w-full rounded-lg border border-outline-gray-2 p-2 text-xs"
              />
            </div>

            <div>
              <label class="block font-medium text-ink-gray-8 mb-1">{{ __('Nội dung bài viết') }}</label>
              <textarea
                v-model="createForm.content"
                rows="6"
                class="w-full rounded-lg border border-outline-gray-2 p-2.5 text-xs text-ink-gray-9 leading-relaxed"
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
    <Dialog v-model:open="showImageModal" :size="'3xl'">
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
import { call, Button, Badge, Dialog, toast } from 'frappe-ui'
import LayoutHeader from '@/components/LayoutHeader.vue'

// Lucide Icons
import MegaphoneIcon from '~icons/lucide/megaphone'
import LucideSparkles from '~icons/lucide/sparkles'
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

// State
const posts = ref([])
const loading = ref(false)
const weeklyMatrix = ref([
  { day: 0, day_of_week: 'Thứ Hai', time: '08:30:00', course: 'Tiếng Anh', default_title: 'Khai giảng Tiếng Anh giao tiếp' },
  { day: 2, day_of_week: 'Thứ Tư', time: '11:30:00', course: 'Toán tư duy', default_title: 'Phát triển tư duy logic' },
  { day: 4, day_of_week: 'Thứ Sáu', time: '19:30:00', course: 'Bơi lội', default_title: 'Khóa bơi sinh tồn cho bé' },
  { day: 6, day_of_week: 'Chủ Nhật', time: '09:00:00', course: 'Chung', default_title: 'Tuyển sinh & Học bổng EduFlow' },
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

// Modals
const showGenerateModal = ref(false)
const showRollbackModal = ref(false)
const showEditModal = ref(false)
const showCreateModal = ref(false)
const showImageModal = ref(false)
const previewImageUrl = ref('')

// Form states
const generateForm = ref({ boss_directive: '' })
const rollbackForm = ref({ new_directive: '' })
const editingPost = ref(null)
const createForm = ref({
  title: '',
  course: 'Tiếng Anh',
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

// Fetch posts list
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
function openEditModal(post) {
  editingPost.value = JSON.parse(JSON.stringify(post))
  showEditModal.value = true
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
    await call('run_doc_method', {
      dt: 'Facebook Post',
      dn: editingPost.value.name,
      method: 'generate_ai_content',
      args: { user_feedback: editingPost.value.ai_feedback || null },
    })
    // Reload doc
    const updated = await call('frappe.client.get', {
      doctype: 'Facebook Post',
      name: editingPost.value.name,
    })
    if (updated) {
      editingPost.value.content = updated.content
      toast.success ? toast.success('AI Gemini đã viết lại nội dung thành công!') : toast.info('Đã viết lại nội dung!')
    }
  } catch (error) {
    console.error('Lỗi AI viết lại:', error)
  } finally {
    rewritingContent.value = false
  }
}

async function handleAiGenerateBanner() {
  if (!editingPost.value) return
  generatingBanner.value = true
  try {
    await call('run_doc_method', {
      dt: 'Facebook Post',
      dn: editingPost.value.name,
      method: 'generate_banner',
      args: { user_feedback: editingPost.value.ai_feedback || null },
    })
    const updated = await call('frappe.client.get', {
      doctype: 'Facebook Post',
      name: editingPost.value.name,
    })
    if (updated) {
      editingPost.value.image = updated.image
      toast.success ? toast.success('AI đã tạo mới Banner chuẩn 1080x1080!') : toast.info('Đã tạo mới Banner!')
    }
  } catch (error) {
    console.error('Lỗi AI tạo banner:', error)
  } finally {
    generatingBanner.value = false
  }
}

// Custom Create Post
function openCreateModal() {
  createForm.value = {
    title: '',
    course: 'Tiếng Anh',
    day_of_week: 'Thứ Hai',
    scheduled_time: '',
    content: '',
  }
  showCreateModal.value = true
}

function openCreateModalForSlot(slot) {
  createForm.value = {
    title: slot.default_title,
    course: slot.course,
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
})
</script>
