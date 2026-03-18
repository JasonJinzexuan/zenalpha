<script setup lang="ts">
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
</script>

<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="logo">
        <h1>ZenAlpha</h1>
        <span class="subtitle">Chan Theory Quantitative Analysis</span>
      </div>
      <el-menu
        mode="horizontal"
        :router="true"
        :default-active="$route.path"
        class="nav-menu"
      >
        <el-menu-item index="/">Dashboard</el-menu-item>
        <el-menu-item index="/analysis">Analysis</el-menu-item>
        <el-menu-item index="/scanner">Scanner</el-menu-item>
        <el-menu-item index="/backtest">Backtest</el-menu-item>
        <el-menu-item index="/settings">Settings</el-menu-item>
      </el-menu>
      <div class="user-info">
        <template v-if="userStore.isAuthenticated">
          <el-dropdown>
            <span class="el-dropdown-link">
              {{ userStore.username }}
              <el-icon><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="userStore.logout()">Logout</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button type="primary" size="small" @click="$router.push('/login')">Login</el-button>
        </template>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', Arial, sans-serif;
  background-color: #0d1117;
  color: #c9d1d9;
}

.app-container {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  background-color: #161b22;
  border-bottom: 1px solid #30363d;
  padding: 0 20px;
}

.logo {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-right: 40px;
}

.logo h1 {
  color: #58a6ff;
  font-size: 20px;
  font-weight: 600;
}

.logo .subtitle {
  color: #8b949e;
  font-size: 12px;
}

.nav-menu {
  flex: 1;
  background-color: transparent;
  border-bottom: none;
}

.nav-menu .el-menu-item {
  color: #c9d1d9;
}

.nav-menu .el-menu-item.is-active {
  color: #58a6ff;
  border-bottom-color: #58a6ff;
}

.user-info {
  margin-left: auto;
}

.el-dropdown-link {
  color: #c9d1d9;
  cursor: pointer;
}

.app-main {
  padding: 20px;
  background-color: #0d1117;
}
</style>
