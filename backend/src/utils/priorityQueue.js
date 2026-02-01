// src/utils/priorityQueue.js
// Min-heap priority queue with decreaseKey support

class PriorityQueue {
  constructor() {
    this.heap = []; // array of { key, priority }
    this.indexMap = new Map(); // key -> index in heap
  }

  size() {
    return this.heap.length;
  }

  isEmpty() {
    return this.size() === 0;
  }

  _swap(i, j) {
    const a = this.heap[i];
    const b = this.heap[j];
    this.heap[i] = b;
    this.heap[j] = a;
    this.indexMap.set(a.key, j);
    this.indexMap.set(b.key, i);
  }

  _siftUp(idx) {
    while (idx > 0) {
      const parent = Math.floor((idx - 1) / 2);
      if (this.heap[parent].priority <= this.heap[idx].priority) break;
      this._swap(parent, idx);
      idx = parent;
    }
  }

  _siftDown(idx) {
    const n = this.size();
    while (true) {
      let left = idx * 2 + 1;
      let right = idx * 2 + 2;
      let smallest = idx;
      if (left < n && this.heap[left].priority < this.heap[smallest].priority) smallest = left;
      if (right < n && this.heap[right].priority < this.heap[smallest].priority) smallest = right;
      if (smallest === idx) break;
      this._swap(idx, smallest);
      idx = smallest;
    }
  }

  push(key, priority) {
    if (this.indexMap.has(key)) {
      // Already present, use decreaseKey if new priority is better
      const i = this.indexMap.get(key);
      if (this.heap[i].priority > priority) {
        this.heap[i].priority = priority;
        this._siftUp(i);
      }
      return;
    }
    const node = { key, priority };
    this.heap.push(node);
    const idx = this.heap.length - 1;
    this.indexMap.set(key, idx);
    this._siftUp(idx);
  }

  decreaseKey(key, newPriority) {
    if (!this.indexMap.has(key)) return this.push(key, newPriority);
    const idx = this.indexMap.get(key);
    if (this.heap[idx].priority <= newPriority) return;
    this.heap[idx].priority = newPriority;
    this._siftUp(idx);
  }

  pop() {
    if (this.isEmpty()) return null;
    const top = this.heap[0];
    const last = this.heap.pop();
    this.indexMap.delete(top.key);
    if (this.heap.length > 0) {
      this.heap[0] = last;
      this.indexMap.set(last.key, 0);
      this._siftDown(0);
    }
    return top;
  }
}

module.exports = PriorityQueue;
