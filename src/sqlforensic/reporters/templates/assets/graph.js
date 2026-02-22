/* SQLForensic — Interactive D3.js Force-Directed Dependency Graph */

function initGraph(containerId, graphData) {
    const container = document.getElementById(containerId);
    if (!container || !graphData || !graphData.nodes || !graphData.nodes.length) {
        container.innerHTML = '<p style="color:#64748b;text-align:center;padding:4rem">No dependency data available</p>';
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;

    const colorMap = {
        table: '#3b82f6',
        procedure: '#8b5cf6',
        view: '#06b6d4',
        unknown: '#64748b'
    };

    const criticalityColor = d3.scaleSequential(d3.interpolateRdYlGn)
        .domain([20, 0]);

    const svg = d3.select('#' + containerId)
        .append('svg')
        .attr('viewBox', [0, 0, width, height]);

    // Add zoom behavior
    const g = svg.append('g');
    const zoom = d3.zoom()
        .scaleExtent([0.1, 5])
        .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    // Tooltip
    const tooltip = d3.select('#' + containerId)
        .append('div')
        .attr('class', 'node-tooltip');

    // Force simulation
    const simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    // Draw links
    const link = g.append('g')
        .attr('class', 'links')
        .selectAll('line')
        .data(graphData.links)
        .join('line')
        .attr('stroke', d => d.type === 'foreign_key' ? '#3b82f6' : '#475569')
        .attr('stroke-opacity', 0.4)
        .attr('stroke-width', d => d.type === 'foreign_key' ? 2 : 1)
        .attr('stroke-dasharray', d => d.type === 'calls' ? '5,5' : null);

    // Draw arrow markers
    svg.append('defs').selectAll('marker')
        .data(['fk', 'ref', 'call'])
        .join('marker')
        .attr('id', d => 'arrow-' + d)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 25)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', d => d === 'fk' ? '#3b82f6' : '#475569')
        .attr('d', 'M0,-5L10,0L0,5');

    link.attr('marker-end', d => {
        if (d.type === 'foreign_key') return 'url(#arrow-fk)';
        if (d.type === 'calls') return 'url(#arrow-call)';
        return 'url(#arrow-ref)';
    });

    // Draw nodes
    const node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('g')
        .data(graphData.nodes)
        .join('g')
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded));

    // Node circles
    node.append('circle')
        .attr('r', d => {
            const base = d.type === 'table' ? 12 : 8;
            return base + Math.min(d.criticality, 15);
        })
        .attr('fill', d => colorMap[d.type] || colorMap.unknown)
        .attr('stroke', d => d.criticality > 10 ? '#ef4444' : '#1e293b')
        .attr('stroke-width', d => d.criticality > 10 ? 2.5 : 1.5)
        .attr('opacity', 0.9);

    // Node labels
    node.append('text')
        .text(d => d.id.length > 16 ? d.id.slice(0, 14) + '..' : d.id)
        .attr('dx', d => (d.type === 'table' ? 16 : 12) + Math.min(d.criticality, 10))
        .attr('dy', 4)
        .attr('fill', '#94a3b8')
        .attr('font-size', '11px')
        .attr('font-family', 'Inter, sans-serif');

    // Hover effects
    node.on('mouseover', function(event, d) {
        // Highlight connected
        const connected = new Set();
        graphData.links.forEach(l => {
            const src = typeof l.source === 'object' ? l.source.id : l.source;
            const tgt = typeof l.target === 'object' ? l.target.id : l.target;
            if (src === d.id) connected.add(tgt);
            if (tgt === d.id) connected.add(src);
        });
        connected.add(d.id);

        node.select('circle').attr('opacity', n => connected.has(n.id) ? 1 : 0.15);
        node.select('text').attr('opacity', n => connected.has(n.id) ? 1 : 0.15);
        link.attr('stroke-opacity', l => {
            const src = typeof l.source === 'object' ? l.source.id : l.source;
            const tgt = typeof l.target === 'object' ? l.target.id : l.target;
            return (src === d.id || tgt === d.id) ? 0.8 : 0.05;
        });

        // Tooltip
        tooltip.classed('visible', true)
            .html(`<strong>${d.id}</strong>Type: ${d.type}<br>Connections: ${d.criticality}`)
            .style('left', (event.offsetX + 15) + 'px')
            .style('top', (event.offsetY - 10) + 'px');
    })
    .on('mouseout', function() {
        node.select('circle').attr('opacity', 0.9);
        node.select('text').attr('opacity', 1);
        link.attr('stroke-opacity', 0.4);
        tooltip.classed('visible', false);
    })
    .on('click', function(event, d) {
        const detail = document.getElementById('node-detail');
        if (detail) {
            const incoming = graphData.links.filter(l => {
                const tgt = typeof l.target === 'object' ? l.target.id : l.target;
                return tgt === d.id;
            });
            const outgoing = graphData.links.filter(l => {
                const src = typeof l.source === 'object' ? l.source.id : l.source;
                return src === d.id;
            });
            detail.innerHTML = `
                <h3 style="color:var(--accent);margin-bottom:0.5rem">${d.id}</h3>
                <p><strong>Type:</strong> ${d.type}</p>
                <p><strong>Incoming:</strong> ${incoming.length} connections</p>
                <p><strong>Outgoing:</strong> ${outgoing.length} connections</p>
                <div style="margin-top:0.5rem">
                    ${incoming.map(l => {
                        const src = typeof l.source === 'object' ? l.source.id : l.source;
                        return `<span class="badge badge-low" style="margin:2px">${src}</span>`;
                    }).join('')}
                </div>
            `;
        }
    });

    // Simulation tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Drag functions
    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    // Filter function (exposed globally)
    window.filterGraph = function(type) {
        if (type === 'all') {
            node.style('display', null);
            link.style('display', null);
        } else {
            node.style('display', d => d.type === type ? null : 'none');
            link.style('display', l => {
                const src = typeof l.source === 'object' ? l.source : graphData.nodes.find(n => n.id === l.source);
                const tgt = typeof l.target === 'object' ? l.target : graphData.nodes.find(n => n.id === l.target);
                return (src && src.type === type) || (tgt && tgt.type === type) ? null : 'none';
            });
        }
    };

    // Reset zoom
    window.resetZoom = function() {
        svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
    };
}
