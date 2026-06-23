<script setup lang="ts">
import {
  Bell,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CirclePlus,
  Cpu,
  Download,
  Edit3,
  Eye,
  EyeOff,
  Folder,
  FolderPlus,
  Gauge,
  Globe2,
  HardDrive,
  Image,
  KeyRound,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Maximize2,
  Menu,
  Minimize2,
  Monitor,
  Network,
  Plus,
  QrCode,
  RefreshCw,
  RotateCcw,
  ScanLine,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SquareTerminal,
  Trash2,
  Upload,
  User,
  Users,
  X,
} from '@lucide/vue';
import { computed } from 'vue';

const props = withDefaults(defineProps<{ name: IconName; size?: number; strokeWidth?: number }>(), {
  size: 18,
  strokeWidth: 2,
});

const icons = {
  alert: CircleAlert,
  bell: Bell,
  check: Check,
  chevronDown: ChevronDown,
  chevronRight: ChevronRight,
  circleCheck: CircleCheck,
  circleHelp: CircleHelp,
  circlePlus: CirclePlus,
  cpu: Cpu,
  dashboard: LayoutDashboard,
  download: Download,
  edit: Edit3,
  eye: Eye,
  eyeOff: EyeOff,
  folder: Folder,
  folderPlus: FolderPlus,
  gauge: Gauge,
  globe: Globe2,
  hardDrive: HardDrive,
  image: Image,
  key: KeyRound,
  lock: LockKeyhole,
  logout: LogOut,
  maximize: Maximize2,
  menu: Menu,
  minimize: Minimize2,
  monitor: Monitor,
  network: Network,
  plus: Plus,
  qr: QrCode,
  refresh: RefreshCw,
  reset: RotateCcw,
  scan: ScanLine,
  search: Search,
  server: Server,
  settings: Settings,
  shield: ShieldCheck,
  terminal: SquareTerminal,
  trash: Trash2,
  upload: Upload,
  user: User,
  users: Users,
  x: X,
};

export type IconName = keyof typeof icons;

const iconComponent = computed(() => icons[props.name]);
</script>

<template>
  <component
    :is="iconComponent"
    class="app-icon"
    :size="size"
    :stroke-width="strokeWidth"
    aria-hidden="true"
  />
</template>
