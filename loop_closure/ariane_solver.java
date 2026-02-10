public void buildGraph(List<Integer> listIndexSelectedClosure) {
    Profiler.start("CaveGeo.buildGraph");
    try {
      graph.clearAll();
      // Add all station to the graph without position
      this.getSurveyData().stream()
          .filter(s -> !s.getType().equals(TypeShot.CLOSURE.name()))
          .forEach(s -> graph.addVertex(new Vertex(s.getID())));

      // Add Start stations
      this.getSurveyData().stream()
          .filter(s -> s.getType().equals(TypeShot.START.name()))
          .forEach(
              s -> {
                Point2D relativelocationofstart =
                    geolocationToMapPaneCoordinates(
                        firstStartLocation, stationGeolocation[s.getID()]);
                final Vertex vertex = graph.findVertex(s.getID());
                vertex.setPosition(
                    new Point3D(relativelocationofstart.getX(), relativelocationofstart.getY(), 0));
                vertex.setTypePosition(TypePosition.FIXED);
              });

      // Add all measured edges
      this.getSurveyData().stream()
          .filter(
              s ->
                  s.getType().equals(TypeShot.REAL.name())
                      || s.getType().equals(TypeShot.VIRTUAL.name()))
          .forEach(
              s -> {
                final Vertex vertexFrom = graph.findVertex(s.getFromID());

                final Vertex vertex = graph.findVertex(s.getID());

                // Vertex might not be present if one of the two doesn't belong to listLoop
                if (vertexFrom != null && vertex != null) {
                  var edge =
                      new DirectedEdge(
                          vertexFrom,
                          vertex,
                          getCoordinateStation(s.getID())
                              .subtract(getCoordinateStation(s.getFromID())),
                          TypeVector.MEASURED,
                          Direction.FORWARD);

                  Point2D relativelocationofstart =
                      geolocationToMapPaneCoordinates(
                          firstStartLocation, stationGeolocation[s.getID()]);

                  vertex.setPosition(
                      new Point3D(
                          relativelocationofstart.getX(), relativelocationofstart.getY(), 0));
                  vertex.setTypePosition(TypePosition.ESTIMATED);
                  graph.addEdge(edge);
                }
              });
      // Point2D shiftstarts =
      // geolocationToMapPaneCoordinates(stationGeolocation[startclosurefromstation.IDStation],
      // stationGeolocation[startclosuretostation.IDStation]);

      // Simplify loops

      // Create station simplification List
      stationSubstitutions.clear();

      substituteStationClosure(listIndexSelectedClosure);
    } catch (Throwable t) {
      Profiler.logException(t);
      throw t;
    } finally {
      Profiler.stop("CaveGeo.buildGraph");
    }
  }

 public void solveLeastSquare() {

    if (CUDASolvers.useCUDA) {
      solveCudaPath();
    } else {
      solveRustGraph();
    }
  }

  private void solveRustGraph() {
    Profiler.start("Graph.solveRustGraph");
    try {
      try {
        int n = vertices.size();
        int m = edges.size();

        Map<Vertex, Integer> vertexIndexMap = new HashMap<>(n);
        for (int i = 0; i < n; i++) {
          vertexIndexMap.put(vertices.get(i), i);
        }

        // Vertices Data
        Profiler.start("Graph.solveRustGraph.VerticesData");
        try (Arena arena = Arena.ofConfined()) {
          MemorySegment xSeg = arena.allocate((long) n * Double.BYTES);
          MemorySegment ySeg = arena.allocate((long) n * Double.BYTES);
          MemorySegment fixedSeg = arena.allocate((long) n * Integer.BYTES);

          for (int i = 0; i < n; i++) {
            Vertex v = vertices.get(i);
            xSeg.set(ValueLayout.JAVA_DOUBLE, (long) i * Double.BYTES, v.position.getX());
            ySeg.set(ValueLayout.JAVA_DOUBLE, (long) i * Double.BYTES, v.position.getY());
            fixedSeg.set(
                ValueLayout.JAVA_INT,
                (long) i * Integer.BYTES,
                v.getTypePosition() == TypePosition.FIXED ? 1 : 0);
          }
          Profiler.stop("Graph.solveRustGraph.VerticesData");

          // Edges Data - Single Pass
          Profiler.start("Graph.solveRustGraph.EdgesData");
          int initialM = edges.size();
          MemorySegment fromSeg = arena.allocate((long) initialM * Integer.BYTES);
          MemorySegment toSeg = arena.allocate((long) initialM * Integer.BYTES);
          MemorySegment dxSeg = arena.allocate((long) initialM * Double.BYTES);
          MemorySegment dySeg = arena.allocate((long) initialM * Double.BYTES);
          MemorySegment wSeg = arena.allocate((long) initialM * Double.BYTES);

          int validEdgeCount = 0;
          for (int i = 0; i < initialM; i++) {
            Edge e = edges.get(i);
            Integer u = vertexIndexMap.get(e.firstVertex);
            Integer v = vertexIndexMap.get(e.secondVertex);

            if (u != null && v != null) {
              fromSeg.set(ValueLayout.JAVA_INT, (long) validEdgeCount * Integer.BYTES, u);
              toSeg.set(ValueLayout.JAVA_INT, (long) validEdgeCount * Integer.BYTES, v);

              double rij = e.vector.magnitude();
              double wij = Math.min(10.0, (rij == 0) ? 10.0 : 1.0 / rij);

              dxSeg.set(
                  ValueLayout.JAVA_DOUBLE, (long) validEdgeCount * Double.BYTES, e.vector.getX());
              dySeg.set(
                  ValueLayout.JAVA_DOUBLE, (long) validEdgeCount * Double.BYTES, e.vector.getY());
              wSeg.set(ValueLayout.JAVA_DOUBLE, (long) validEdgeCount * Double.BYTES, wij);

              validEdgeCount++;
            }
          }
          m = validEdgeCount;
          Profiler.stop("Graph.solveRustGraph.EdgesData");

          if (solveHandle == null) initFFI();

          if (solveHandle != null) {
            int iterations = Integer.getInteger("ariane.iterations", 60000);
            // solve_graph_least_squares(n, x, y, fixed, m, from, to, dx, dy, w, iter, tol)
            Profiler.start("Graph.solveRustGraph.NativeCall");
            int result =
                (int)
                    solveHandle.invokeExact(
                        n,
                        xSeg,
                        ySeg,
                        fixedSeg,
                        m,
                        fromSeg,
                        toSeg,
                        dxSeg,
                        dySeg,
                        wSeg,
                        iterations,
                        0.001);
            Profiler.stop("Graph.solveRustGraph.NativeCall");

            if (result != 0) {
              throw new RuntimeException("Native solver failed with error code: " + result);
            }

            // Read back results
            Profiler.start("Graph.solveRustGraph.UpdateResults");
            for (int i = 0; i < n; i++) {
              Vertex v = vertices.get(i);
              if (v.getTypePosition() != TypePosition.FIXED) {
                double newX = xSeg.get(ValueLayout.JAVA_DOUBLE, (long) i * Double.BYTES);
                double newY = ySeg.get(ValueLayout.JAVA_DOUBLE, (long) i * Double.BYTES);

                Point3D corrected = new Point3D(newX, newY, v.position.getZ());
                v.setCorrection(corrected.subtract(v.getPosition()));
                v.setPosition(corrected);
                v.setTypePosition(TypePosition.ADJUSTED);
              }
            }
            Profiler.stop("Graph.solveRustGraph.UpdateResults");
          }
        }
      } catch (Throwable t) {
        Profiler.logException(t);
        LOG.log(java.util.logging.Level.SEVERE, null, t);
      }
    } finally {
      Profiler.stop("Graph.solveRustGraph");
    }
  }