<script>
  /**
   * WideScroll — zone défilante avec un ascenseur latéral large et doré.
   * Firefox ne permet pas d'élargir l'ascenseur natif (au mieux « auto ») :
   * on masque donc le natif et on dessine notre propre rail, qu'on peut
   * saisir à la souris, cliquer pour avancer d'une page, ou piloter à la
   * molette comme d'habitude. (version française, F1NSK)
   */
  import { onMount, onDestroy } from "svelte";

  export let width = 20;          // largeur du rail en px
  let klass = "";
  export { klass as class };

  let box, rail;
  let thumbH = 0, thumbTop = 0, needed = false;
  let ro, mo;

  function update() {
    if (!box || !rail) return;
    const h = box.clientHeight, sh = box.scrollHeight, rh = rail.clientHeight;
    needed = sh > h + 1;
    if (!needed) return;
    thumbH = Math.max(36, (h / sh) * rh);
    thumbTop = (box.scrollTop / (sh - h)) * (rh - thumbH);
  }

  let dragging = false, startY = 0, startTop = 0;
  function down(ev) {
    ev.preventDefault();
    dragging = true;
    startY = ev.clientY;
    startTop = box.scrollTop;
    ev.currentTarget.setPointerCapture(ev.pointerId);
  }
  function move(ev) {
    if (!dragging) return;
    const rh = rail.clientHeight;
    const ratio = (box.scrollHeight - box.clientHeight) / Math.max(1, rh - thumbH);
    box.scrollTop = startTop + (ev.clientY - startY) * ratio;
  }
  function up() { dragging = false; }
  function railClick(ev) {
    if (ev.target !== rail) return;
    const y = ev.clientY - rail.getBoundingClientRect().top;
    box.scrollTop += (y < thumbTop ? -1 : 1) * box.clientHeight * 0.9;
  }

  onMount(() => {
    ro = new ResizeObserver(update);
    ro.observe(box);
    mo = new MutationObserver(update);
    mo.observe(box, { childList: true, subtree: true, characterData: true });
    box.addEventListener("load", update, true);   // images chargées
    update();
  });
  onDestroy(() => { ro && ro.disconnect(); mo && mo.disconnect(); });
</script>

<div class="ws-wrap {klass}">
  <div class="ws-box" bind:this={box} on:scroll={update}><slot /></div>
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="ws-rail" class:off={!needed} bind:this={rail} style="width:{width}px" on:click={railClick}>
    <div
      class="ws-thumb" class:drag={dragging}
      style="height:{thumbH}px; transform:translateY({thumbTop}px)"
      on:pointerdown={down} on:pointermove={move} on:pointerup={up} on:pointercancel={up}
    ></div>
  </div>
</div>

<style>
  .ws-wrap { display: flex; min-height: 0; min-width: 0; position: relative; }
  .ws-box {
    flex: 1; min-width: 0; overflow-y: auto; overflow-x: hidden;
    scrollbar-width: none;
  }
  .ws-box::-webkit-scrollbar { display: none; }
  .ws-rail {
    flex: none; position: relative; cursor: pointer;
    background: rgba(255, 255, 255, 0.05);
    border-left: 1px solid #374151;
  }
  .ws-rail.off { visibility: hidden; }
  .ws-thumb {
    position: absolute; left: 3px; right: 3px; top: 0;
    border-radius: 6px; cursor: grab; touch-action: none;
    background: rgba(207, 181, 59, 0.55);
    box-shadow: inset 0 0 0 1px rgba(207, 181, 59, 0.9);
  }
  .ws-thumb:hover { background: rgba(207, 181, 59, 0.75); }
  .ws-thumb.drag { background: rgb(207, 181, 59); cursor: grabbing; }
</style>
