import { onUnmounted } from 'vue';

interface LoginCatAnimationTargets {
  getPanel: () => HTMLElement | null;
  getSvg: () => SVGSVGElement | null;
  getUsernameInput: () => HTMLInputElement | null;
  getPasswordInput: () => HTMLInputElement | null;
}

export function useLoginCatAnimation(targets: LoginCatAnimationTargets) {
  let cleanupCatAnimation: (() => void) | undefined;

  function start() {
    cleanupCatAnimation?.();

    const panel = targets.getPanel();
    const svg = targets.getSvg();
    const userInput = targets.getUsernameInput();
    const passInput = targets.getPasswordInput();
    if (!panel || !svg || !userInput || !passInput) return;

    const pupilNodes = Array.from(svg.querySelectorAll<SVGGElement>('.cat-pupil'));
    const headGroup = svg.querySelector<SVGGElement>('.cat-head-group');
    const neckGroup = svg.querySelector<SVGGElement>('.cat-neck-group');
    const whiskersGroup = svg.querySelector<SVGGElement>('.cat-whiskers-group');
    if (!pupilNodes.length || !headGroup || !neckGroup) return;

    const pupils = pupilNodes.map((node) => ({
      node,
      cx: Number(node.dataset.eyeX),
      cy: Number(node.dataset.eyeY),
      x: 0,
      y: 0,
      targetX: 0,
      targetY: 0,
    }));

    const pose = {
      headX: 0,
      headY: 0,
      headRot: 0,
      neckX: 0,
      neckY: 0,
      neckRot: 0,
      neckScale: 1,
      whiskerX: 0,
      whiskerRot: 0,
      targetHeadX: 0,
      targetHeadY: 0,
      targetHeadRot: 0,
      targetNeckX: 0,
      targetNeckY: 0,
      targetNeckRot: 0,
      targetNeckScale: 1,
      targetWhiskerX: 0,
      targetWhiskerRot: 0,
    };

    const maxMoveNormal = 7.5;
    const maxMovePeek = 8.5;
    const influenceRange = 145;
    let pointerInside = false;
    let lastFrameTime = performance.now();
    let lastPointer: { x: number; y: number; time: number } | null = null;
    let pointerSpeed = 0;
    let usernameFocused = false;
    let frameId = 0;

    function clamp(value: number, min: number, max: number) {
      return Math.max(min, Math.min(max, value));
    }

    function clientToSvgPoint(clientX: number, clientY: number) {
      const matrix = svg.getScreenCTM();
      if (!matrix) return null;

      const point = svg.createSVGPoint();
      point.x = clientX;
      point.y = clientY;
      return point.matrixTransform(matrix.inverse());
    }

    function pointEyesAt(clientX: number, clientY: number, maxMove: number) {
      const target = clientToSvgPoint(clientX, clientY);
      if (!target) return;

      pupils.forEach((eye) => {
        const dx = target.x - eye.cx;
        const dy = target.y - eye.cy;
        const distance = Math.hypot(dx, dy) || 1;
        const strength = clamp(distance / influenceRange, 0, 1);
        eye.targetX = (dx / distance) * maxMove * strength;
        eye.targetY = (dy / distance) * maxMove * strength;
      });
    }

    function updatePointerSpeed(clientX: number, clientY: number) {
      const now = performance.now();
      if (!lastPointer) {
        lastPointer = { x: clientX, y: clientY, time: now };
        pointerSpeed = 0;
        return;
      }

      const dx = clientX - lastPointer.x;
      const dy = clientY - lastPointer.y;
      const dt = Math.max(now - lastPointer.time, 8);
      pointerSpeed = (Math.hypot(dx, dy) / dt) * 1000;
      lastPointer = { x: clientX, y: clientY, time: now };
    }

    function updateFromLeftPanelPointer(event: PointerEvent) {
      updatePointerSpeed(event.clientX, event.clientY);
      pointEyesAt(event.clientX, event.clientY, maxMoveNormal);
    }

    function updatePeekToUsername() {
      const rect = userInput.getBoundingClientRect();
      pointEyesAt(rect.left + rect.width * 0.24, rect.top + rect.height * 0.5, maxMovePeek);
    }

    function updatePoseTargets() {
      if (usernameFocused) {
        pose.targetHeadX = 28;
        pose.targetHeadY = -12;
        pose.targetHeadRot = 6.5;
        pose.targetNeckX = 24;
        pose.targetNeckY = -1;
        pose.targetNeckRot = -20;
        pose.targetNeckScale = 1.82;
        pose.targetWhiskerX = 10;
        pose.targetWhiskerRot = 5;
        updatePeekToUsername();
        return;
      }

      pose.targetHeadX = 0;
      pose.targetHeadY = 0;
      pose.targetHeadRot = 0;
      pose.targetNeckX = 0;
      pose.targetNeckY = 0;
      pose.targetNeckRot = 0;
      pose.targetNeckScale = 1;
      pose.targetWhiskerX = 0;
      pose.targetWhiskerRot = 0;

      if (!pointerInside) {
        pupils.forEach((eye) => {
          eye.targetX = 0;
          eye.targetY = 0;
        });
      }
    }

    function applyTransforms() {
      headGroup.setAttribute('transform', `translate(${pose.headX.toFixed(2)} ${pose.headY.toFixed(2)}) rotate(${pose.headRot.toFixed(2)} 210 188)`);
      neckGroup.setAttribute(
        'transform',
        `translate(${pose.neckX.toFixed(2)} ${pose.neckY.toFixed(2)}) rotate(${pose.neckRot.toFixed(2)} 210 196) translate(210 196) scale(1 ${pose.neckScale.toFixed(3)}) translate(-210 -196)`
      );
      whiskersGroup?.setAttribute('transform', `translate(${pose.whiskerX.toFixed(2)} 0) rotate(${pose.whiskerRot.toFixed(2)} 210 214)`);
      pupils.forEach((eye) => {
        eye.node.setAttribute('transform', `translate(${eye.x.toFixed(2)} ${eye.y.toFixed(2)})`);
      });
    }

    function animate(now: number) {
      const delta = Math.min(now - lastFrameTime, 34);
      lastFrameTime = now;
      updatePoseTargets();

      const speedEase = clamp(pointerSpeed / 2600, 0, 0.36);
      const eyesBaseEase = usernameFocused ? 0.26 : pointerInside ? 0.3 + speedEase : 0.12;
      const bodyBaseEase = usernameFocused ? 0.22 : 0.14;
      const eyesEase = 1 - Math.pow(1 - eyesBaseEase, delta / 16.67);
      const bodyEase = 1 - Math.pow(1 - bodyBaseEase, delta / 16.67);

      pupils.forEach((eye) => {
        eye.x += (eye.targetX - eye.x) * eyesEase;
        eye.y += (eye.targetY - eye.y) * eyesEase;
      });

      pose.headX += (pose.targetHeadX - pose.headX) * bodyEase;
      pose.headY += (pose.targetHeadY - pose.headY) * bodyEase;
      pose.headRot += (pose.targetHeadRot - pose.headRot) * bodyEase;
      pose.neckX += (pose.targetNeckX - pose.neckX) * bodyEase;
      pose.neckY += (pose.targetNeckY - pose.neckY) * bodyEase;
      pose.neckRot += (pose.targetNeckRot - pose.neckRot) * bodyEase;
      pose.neckScale += (pose.targetNeckScale - pose.neckScale) * bodyEase;
      pose.whiskerX += (pose.targetWhiskerX - pose.whiskerX) * bodyEase;
      pose.whiskerRot += (pose.targetWhiskerRot - pose.whiskerRot) * bodyEase;

      applyTransforms();
      pointerSpeed *= 0.86;
      frameId = requestAnimationFrame(animate);
    }

    const handlePointerEnter = (event: PointerEvent) => {
      pointerInside = true;
      if (!usernameFocused) updateFromLeftPanelPointer(event);
    };
    const handlePointerMove = (event: PointerEvent) => {
      pointerInside = true;
      if (!usernameFocused) updateFromLeftPanelPointer(event);
    };
    const handlePointerLeave = () => {
      pointerInside = false;
      lastPointer = null;
      pointerSpeed = 0;
    };
    const handleUsernameFocus = () => {
      usernameFocused = true;
    };
    const handleUsernameBlur = () => {
      usernameFocused = false;
    };
    const handlePasswordFocus = () => {
      usernameFocused = false;
    };

    panel.addEventListener('pointerenter', handlePointerEnter);
    panel.addEventListener('pointermove', handlePointerMove);
    panel.addEventListener('pointerleave', handlePointerLeave);
    userInput.addEventListener('focus', handleUsernameFocus);
    userInput.addEventListener('blur', handleUsernameBlur);
    userInput.addEventListener('pointerdown', handleUsernameFocus);
    passInput.addEventListener('focus', handlePasswordFocus);
    frameId = requestAnimationFrame(animate);

    cleanupCatAnimation = () => {
      cancelAnimationFrame(frameId);
      panel.removeEventListener('pointerenter', handlePointerEnter);
      panel.removeEventListener('pointermove', handlePointerMove);
      panel.removeEventListener('pointerleave', handlePointerLeave);
      userInput.removeEventListener('focus', handleUsernameFocus);
      userInput.removeEventListener('blur', handleUsernameBlur);
      userInput.removeEventListener('pointerdown', handleUsernameFocus);
      passInput.removeEventListener('focus', handlePasswordFocus);
    };
  }

  function stop() {
    cleanupCatAnimation?.();
    cleanupCatAnimation = undefined;
  }

  onUnmounted(stop);

  return { start, stop };
}
