/* Copyright 2019 The TensorFlow Authors. All Rights Reserved.
Licensed under the Apache License, Version 2.0 (the 'License');
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an 'AS IS' BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================*/

namespace pod_viewer_stack_bar_chart {

const BAR_WIDTH = 50;
const SVG_HEIGHT = 300;
const SVG_MIN_WIDTH = 1600;

Polymer({
  is: 'stack-bar-chart',
  properties: {
    id: {
      type: String,
    },
    data: {
      type: Object,
      observer: '_dataChanged',
    },
    activeBar: {
      type: Object,
      notify: true,
    },
    xDomainFunc: {
      type: Object,
      notify: true,
    },
    stackLayers: {
      type: Array,
      notify: true,
      observer: '_onStackLayersChanged',
    },
    _ready: {
      type: Boolean,
      value: false,
    },
  },
  /**
   * Main function to draw a stacked bar chart.
   */
  stackBarChart: function(data) {
    if (!data || !this._ready || this.stackLayers.length == 0) {
      return;
    }
    d3.select(this).selectAll('g > *').remove();
    d3.select(this).select('svg').remove();
    d3.select(this).select('.svg-container').remove();
    const stackKey = this.stackLayers.map((d) => d.key);
    const stackLabel = this.stackLayers.map((d) => d.label);
    const margin = {top: 20, right: 20, bottom: 30, left: 100};
    const width = SVG_MIN_WIDTH - margin.left - margin.right;
    const height = SVG_HEIGHT - margin.top - margin.bottom;
    const xScaleRange = data.length * BAR_WIDTH;
    let xScale = d3.scaleBand().range([0, xScaleRange]).padding(0.4);
    let yScale = d3.scaleLinear().range([height, 0]);
    let colorScale = d3.scaleOrdinal<number, string>(d3.schemeCategory10)
                       .domain([0, 19]);
    let svg = d3.select(this.$.chart)
                .append('svg')
                .attr('width',
                      Math.max(SVG_MIN_WIDTH,
                               xScaleRange + margin.left + margin.right))
                .attr('height', SVG_HEIGHT)
                .append('g')
                .attr('transform',
                      'translate(' + margin.left + ',' + margin.top + ')');
    let stack = d3.stack()
                  .keys(stackKey)
                  .order(d3.stackOrderNone)
                  .offset(d3.stackOffsetNone);
    const layers = stack(data);
    xScale.domain(data.map(this.xDomainFunc));
    yScale.domain([0, d3.max(layers[layers.length - 1], (d) => d[0] + d[1])])
          .nice();
    this.drawLayers(svg, layers, xScale, yScale, colorScale);
    this.drawAxes(svg, xScale, yScale, height);
    this.drawLegend(svg, stackLabel, colorScale);
  },
  /**
   * Draw the layers for all the bars.
   */
  drawLayers: function(svg, layers, xScale, yScale, colorScale) {
    let parent = this;
    let layer = svg.selectAll('.layer')
                   .data(layers)
                   .enter()
                   .append('g')
                   .attr('class', 'layer')
                   .style('fill', (d, i) => colorScale(i));
    layer.selectAll('rect')
         .data((d) => d)
         .enter()
         .append('rect')
         .attr('width', xScale.bandwidth())
         .attr('y', (d) => yScale(d[1]))
         .attr('height', (d) => yScale(d[0]) - yScale(d[1]))
         .attr('x', (d, i) => xScale(parent.xDomainFunc(d.data)))
         .on('mouseover',
             function(d) {
               d3.select(this).style('opacity', 0.5);
               parent.activeBar = d.data;
             })
         .on('mouseout', function(d) {
             d3.select(this).style('opacity', 1.0);
             parent.activeBar = null;
         });
  },
  /**
   * Draw the axes of the chart.
   */
  drawAxes: function(svg, xScale, yScale, height) {
    let xAxis = d3.axisBottom(xScale);
    let yAxis = d3.axisLeft(yScale);
    svg.append('g')
       .attr('class', 'axis axis--x')
       .style('font-size', 14)
       .attr('transform', 'translate(0,' + (height + 5) + ')')
       .call(xAxis);
    svg.append('g')
       .attr('class', 'axis axis--y')
       .style('font-size', 14)
       .attr('transform', 'translate(0,0)')
       .call(yAxis);
  },
  /**
   * Draw the legends of the chart.
   */
  drawLegend: function(svg, labels, colorScale) {
    const legendWidth = 150;
    const legendHeight = 30;
    const iconSize = 19;
    const labelsPerLane = 5;
    const margin = 5;
    const yAxisToLegend = 200;
    let legend =
        svg.append('g')
           .attr('font-family', 'sans-serif')
           .attr('font-size', 14)
           .attr('text-anchor', 'start')
           .selectAll('g')
           .data(labels.slice())
           .enter()
           .append('g')
           .attr('transform',
                 (d, i) => 'translate(' +
                     (i * legendWidth -
                       Math.floor(i / labelsPerLane) * legendWidth *
                         labelsPerLane) + ',' +
                           Math.floor(i / labelsPerLane) * legendHeight + ')');
    legend.append('rect')
          .attr('x', yAxisToLegend)
          .attr('width', iconSize)
          .attr('height', iconSize)
          .attr('fill', (d, i) => colorScale(i));
    legend.append('text')
          .attr('x', yAxisToLegend + margin + iconSize)
          .attr('y', 9.5)
          .attr('dy', '0.32em')
          .text((d) => d);
  },
  /**
   * Redraw the stack bar chart.
   */
  redraw: function(data) {
    if (!data) {
      return;
    }
    this.stackBarChart(data);
  },
  /**
   * Redraws the stack bar chart when the stack elements changed.
   */
  _onStackLayersChanged: function(newData) {
    if (!newData || newData.length == 0) {
      return;
    }
    this.redraw(this.data);
  },
  /**
   * Redraws the stack bar chart when the input data changed.
   */
  _dataChanged: function(newData) {
    if (!newData) {
      return;
    }
    this.redraw(newData);
  },
  attached: function() {
    this._ready = true;
    this.redraw(this.data);
  },
});

} // namespace pod_viewer_stack_bar_chart
