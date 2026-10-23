// When the browser skips a page transition its promises reject; the navigation itself completes normally.
// Loaded as a classic script in <head> so the listener exists before "pagereveal" fires.
const ignoreSkippedTransition = ({ viewTransition }) => {
  if (!viewTransition) return;
  [viewTransition.ready, viewTransition.updateCallbackDone, viewTransition.finished].forEach((step) => step.catch(() => {}));
};
addEventListener("pageswap", ignoreSkippedTransition);
addEventListener("pagereveal", ignoreSkippedTransition);
