<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()

const notificationConfig = ref({
  emailEnabled: false,
  emailTarget: '',
  webhookEnabled: false,
  webhookUrl: '',
  minScore: 50,
  signalTypes: ['B1', 'S1'] as string[],
})

const allSignalTypes = ['B1', 'B2', 'B3', 'S1', 'S2', 'S3']

function saveNotificationConfig() {
  ElMessage.success('Notification settings saved')
}

const defaultWatchlist = ref('')

function addToWatchlist() {
  if (!defaultWatchlist.value.trim()) return
  ElMessage.success(`Added ${defaultWatchlist.value} to watchlist`)
  defaultWatchlist.value = ''
}
</script>

<template>
  <div class="settings">
    <h2>Settings</h2>

    <el-card shadow="never" class="settings-card">
      <template #header>User Profile</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="Username">
          {{ userStore.username ?? 'Not logged in' }}
        </el-descriptions-item>
        <el-descriptions-item label="Role">
          {{ userStore.role ?? 'N/A' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="settings-card">
      <template #header>Notification Settings</template>
      <el-form label-width="140px">
        <el-form-item label="Email Alerts">
          <el-switch v-model="notificationConfig.emailEnabled" />
        </el-form-item>
        <el-form-item v-if="notificationConfig.emailEnabled" label="Email Address">
          <el-input v-model="notificationConfig.emailTarget" placeholder="you@example.com" />
        </el-form-item>
        <el-form-item label="Webhook Alerts">
          <el-switch v-model="notificationConfig.webhookEnabled" />
        </el-form-item>
        <el-form-item v-if="notificationConfig.webhookEnabled" label="Webhook URL">
          <el-input v-model="notificationConfig.webhookUrl" placeholder="https://hooks.slack.com/..." />
        </el-form-item>
        <el-form-item label="Signal Types">
          <el-checkbox-group v-model="notificationConfig.signalTypes">
            <el-checkbox v-for="t in allSignalTypes" :key="t" :value="t">{{ t }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="Min Score">
          <el-slider v-model="notificationConfig.minScore" :min="0" :max="100" :step="5" style="width: 300px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveNotificationConfig">Save</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="settings-card">
      <template #header>Quick Add to Watchlist</template>
      <el-form inline>
        <el-form-item>
          <el-input v-model="defaultWatchlist" placeholder="Symbol" @keyup.enter="addToWatchlist" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="addToWatchlist">Add</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings {
  max-width: 800px;
  margin: 0 auto;
}

.settings h2 {
  color: #c9d1d9;
  margin-bottom: 20px;
}

.settings-card {
  background-color: #161b22;
  border-color: #30363d;
  margin-bottom: 20px;
}
</style>
