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

  parent(i) {
    return Math.floor((i-1)/2);
  }

  left(i) {
    return 2*i+1;
  }

  right(i) {
    return 2*i+2;
  }

  contain(key) {
    return this.indexMap.has(key);
  }

  exchange(i, j) {
    const a = this.heap[i];
    const b = this.heap[j];
    this.heap[i] = b;
    this.heap[j] = a;
    this.indexMap.set(a.key, j);
    this.indexMap.set(b.key, i);
  }

  Min_Heapify(i) {
    const l = this.left(i);
    const r = this.right(i);
    let smallest = i;
    if (l < this.size() && this.heap[l].priority < this.heap[smallest].priority) {
      smallest = l;
    }
    if (r < this.size() && this.heap[r].priority < this.heap[smallest].priority) {
      smallest = r;
    }
    if (smallest !== i) {
      this.exchange(i, smallest);
      this.Min_Heapify(smallest);
    }
  }

  pop() {
    if (this.size() === 0) {
      // empty heap
      return null;
    }
    this.exchange(0, this.size()-1);
    const min = this.heap.pop();
    this.indexMap.delete(min.key);
    if (this.size() > 0) this.Min_Heapify(0);
    return min;
  }

  Decrease_Key(i, value) {
    if (value > this.heap[i].priority) {
      return;
    }
    this.heap[i].priority = value;
    while (i > 0 && this.heap[this.parent(i)].priority > this.heap[i].priority) {
      const p = this.parent(i);
      this.exchange(i, p);
      i = p;
    }
  }

  push(key, priority) {
    if (this.indexMap.has(key)) {
      // Already present, use decreaseKey if new priority is smaller
      const i = this.indexMap.get(key);
      if (this.heap[i].priority > priority) {
        this.Decrease_Key(i,priority);
      }
      return;
    }
    const node = { key, priority };
    this.heap.push(node);
    const i = this.heap.length - 1;
    this.indexMap.set(key, i);
    this.Decrease_Key(i,priority);
  }
}

module.exports = PriorityQueue;
