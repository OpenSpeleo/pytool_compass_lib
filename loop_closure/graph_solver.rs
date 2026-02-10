use nalgebra::DVector;
use nalgebra_sparse::{CooMatrix, CsrMatrix};
use std::ffi::{c_double, c_int};
use std::slice;

/// Solves a graph Least Squares adjustment problem for 2D coordinates (X, Y).
///
/// This function is designed to be called from Java via FFI (Project Panama).
/// It takes a set of vertices (some fixed, some free) and edges (constraints between vertices).
/// It constructs a system of linear equations `Ax = b` and solves it using the Conjugate Gradient (CG) method.
///
/// # Arguments
///
/// * `num_vertices` - Total number of vertices in the graph.
/// * `x` - Pointer to the array of X coordinates. Input: Initial guess. Output: Optimized X coordinates.
/// * `y` - Pointer to the array of Y coordinates. Input: Initial guess. Output: Optimized Y coordinates.
/// * `fixed` - Pointer to the array of fixed flags. 1 = Fixed (anchor), 0 = Free (to be adjusted).
/// * `num_edges` - Total number of edges (constraints).
/// * `from` - Pointer to the array of start vertex indices for each edge.
/// * `to` - Pointer to the array of end vertex indices for each edge.
/// * `observed_dx` - Pointer to the array of observed X differences (dx) for each edge.
/// * `observed_dy` - Pointer to the array of observed Y differences (dy) for each edge.
/// * `weight` - Pointer to the array of weights for each edge (typically 1/length or 1/variance).
/// * `iterations` - Maximum number of iterations for the Conjugate Gradient solver.
/// * `tolerance` - Residual tolerance for convergence of the CG solver.
#[unsafe(no_mangle)]
pub extern "C" fn solve_graph_least_squares(
    num_vertices: c_int,
    x: *mut c_double,    // In/Out: Initial guess / Result
    y: *mut c_double,    // In/Out: Initial guess / Result
    fixed: *const c_int, // 0 = Free, 1 = Fixed
    num_edges: c_int,
    from: *const c_int,
    to: *const c_int,
    observed_dx: *const c_double,
    observed_dy: *const c_double,
    weight: *const c_double,
    iterations: c_int,
    tolerance: c_double,
) -> c_int {
    let result = std::panic::catch_unwind(|| {
        if iterations == -1 {
            panic!("Intentional test panic triggered!");
        }
        let n_verts = num_vertices as usize;
        let n_edges = num_edges as usize;

        // Safety: Creating Rust slices from raw C pointers.
        // We assume the caller (Java) guarantees valid non-null pointers and correct lengths.
        let x_slice = unsafe { slice::from_raw_parts_mut(x, n_verts) };
        let y_slice = unsafe { slice::from_raw_parts_mut(y, n_verts) };
        let fixed_slice = unsafe { slice::from_raw_parts(fixed, n_verts) };

        let from_slice = unsafe { slice::from_raw_parts(from, n_edges) };
        let to_slice = unsafe { slice::from_raw_parts(to, n_edges) };
        let dx_slice = unsafe { slice::from_raw_parts(observed_dx, n_edges) };
        let dy_slice = unsafe { slice::from_raw_parts(observed_dy, n_edges) };
        let w_slice = unsafe { slice::from_raw_parts(weight, n_edges) };

        // 1. Mapping: Original Index -> Reduced Index
        // Fixed vertices do not participate in the matrix as variables; they act as boundary conditions.
        // We create a mapping where `mapping[original_index] = Some(reduced_index)` for free vertices,
        // and `None` for fixed vertices.
        let mut mapping = vec![None; n_verts];
        let mut active_count = 0;

        for i in 0..n_verts {
            if fixed_slice[i] == 0 {
                mapping[i] = Some(active_count);
                active_count += 1;
            }
        }

        if active_count == 0 {
            return 0; // No free vertices to adjust, nothing to solve.
        }

        // 2. Assemble Matrix (COO format) and RHS vectors
        // The system to solve is (A^T W A) x = A^T W l, which reduces to a symmetric positive definite system.
        // Here we construct the Normal Equations directly.
        let mut coo_ax = CooMatrix::new(active_count, active_count);

        // Ax and Ay matrices are identical in structure and values (dependent only on weights),
        // so we only need to construct one matrix `coo_ax`.

        let mut bx = DVector::zeros(active_count);
        let mut by = DVector::zeros(active_count);

        // Initial guess vectors for the solver (mapped from input)
        let mut x0_solver = DVector::zeros(active_count);
        let mut y0_solver = DVector::zeros(active_count);

        // Fill initial guess from input slices
        for i in 0..n_verts {
            if let Some(idx) = mapping[i] {
                x0_solver[idx] = x_slice[i];
                y0_solver[idx] = y_slice[i];
            }
        }

        // Iterate over all edges to build the matrix and RHS vectors
        for e in 0..n_edges {
            let u = from_slice[e] as usize;
            let v = to_slice[e] as usize;
            let w = w_slice[e]; // Weight of the observation
            let dx = dx_slice[e];
            let dy = dy_slice[e];

            // An edge between u and v provides an observation:
            // x_v - x_u = dx
            // y_v - y_u = dy
            //
            // In the normal equations (Least Squares), this contributes:
            // A[u, u] += w, A[v, v] += w
            // A[u, v] -= w, A[v, u] -= w
            // RHS_u -= w * dx
            // RHS_v += w * dx

            let u_map = mapping[u];
            let v_map = mapping[v];

            match (u_map, v_map) {
                (Some(ui), Some(vi)) => {
                    // Case 1: Both vertices are free.
                    // Add terms to the matrix for both u and v.
                    coo_ax.push(ui, ui, w);
                    coo_ax.push(vi, vi, w);
                    coo_ax.push(ui, vi, -w);
                    coo_ax.push(vi, ui, -w);

                    // Add terms to RHS vectors
                    bx[ui] -= w * dx;
                    bx[vi] += w * dx;

                    by[ui] -= w * dy;
                    by[vi] += w * dy;
                }
                (Some(ui), None) => {
                    // Case 2: u is free, v is fixed.
                    // Since v is fixed, x_v and y_v are constants.
                    // Terms involving x_v move to the RHS.
                    // A[u, u] += w
                    // A[u, v] * x_v (where A[u,v] is -w) becomes -(-w * x_v) = +w * x_v on the RHS.

                    coo_ax.push(ui, ui, w);

                    // RHS modifications from edge constraint (dx/dy)
                    bx[ui] -= w * dx;
                    by[ui] -= w * dy;

                    // RHS modifications from the fixed neighbor v
                    let xv = x_slice[v];
                    let yv = y_slice[v];

                    bx[ui] += w * xv;
                    by[ui] += w * yv;
                }
                (None, Some(vi)) => {
                    // Case 3: u is fixed, v is free.
                    // Similar to Case 2, but for v.
                    // A[v, v] += w
                    // A[v, u] * x_u (where A[v,u] is -w) becomes -(-w * x_u) = +w * x_u on the RHS.

                    coo_ax.push(vi, vi, w);

                    // RHS modifications from edge constraint
                    bx[vi] += w * dx;
                    by[vi] += w * dy;

                    // RHS modifications from the fixed neighbor u
                    let xu = x_slice[u];
                    let yu = y_slice[u];

                    bx[vi] += w * xu;
                    by[vi] += w * yu;
                }
                (None, None) => {
                    // Case 4: Both fixed.
                    // This is a check constraint between two anchors. It does not affect the system
                    // of equations for the free variables, so we ignore it.
                }
            }
        }

        // Convert COO to CSR format for efficient multiplication in the solver
        let csr_a = CsrMatrix::from(&coo_ax);

        // 3. Solve (Conjugate Gradient)
        // Since X and Y coordinates are independent in this formulation (no rotation/scale parameters),
        // key optimization: we can solve for X and Y in parallel.
        let (res_x, res_y) = std::thread::scope(|s| {
            let handle_x = s.spawn(|| solve_cg(&csr_a, &bx, &x0_solver, iterations, tolerance));
            let handle_y = s.spawn(|| solve_cg(&csr_a, &by, &y0_solver, iterations, tolerance));

            let res_x = handle_x.join().unwrap();
            let res_y = handle_y.join().unwrap();
            (res_x, res_y)
        });

        // 4. Write back results to the original arrays (Java memory)
        for i in 0..n_verts {
            if let Some(idx) = mapping[i] {
                x_slice[i] = res_x[idx];
                y_slice[i] = res_y[idx];
            }
        }
        0
    });

    match result {
        Ok(code) => code,
        Err(_) => {
            eprintln!("Panic caught in solve_graph_least_squares");
            -1
        }
    }
}

/// Solves linear system Ax = b using the Conjugate Gradient method.
///
/// Use this for Symmetric Positive Definite matrices (which the Normal Equations matrix always is).
///
/// # Arguments
///
/// * `a` - The matrix A (CSR format).
/// * `b` - The RHS vector b.
/// * `x0` - Initial guess for x.
/// * `max_iter` - Maximum number of iterations.
/// * `tol` - Tolerance for convergence (based on residual norm).
///
/// # Returns
///
/// * `DVector<f64>` - The solution vector x.
fn solve_cg(
    a: &CsrMatrix<f64>,
    b: &DVector<f64>,
    x0: &DVector<f64>,
    max_iter: c_int,
    tol: f64,
) -> DVector<f64> {
    let mut x = x0.clone();

    // Initial residual r = b - A * x
    // We can allow one allocation here for startup
    let mut r = b - a * &x;

    let mut p = r.clone();

    // Pre-allocate workspace for A * p
    let mut ap = DVector::zeros(x.len());

    let mut rho_old = r.dot(&r);

    for _ in 0..max_iter {
        // Check convergence
        if rho_old.sqrt() < tol {
            break;
        }

        // ap = A * p
        // Optimized to avoid allocation
        spmv_csr(a, &p, &mut ap);

        let p_dot_ap = p.dot(&ap);
        if p_dot_ap.abs() < 1e-15 {
            break;
        } // Safety against division by zero

        let alpha = rho_old / p_dot_ap; // Step size alpha

        // x += alpha * p
        x.axpy(alpha, &p, 1.0);

        // r -= alpha * ap
        r.axpy(-alpha, &ap, 1.0);

        let rho_new = r.dot(&r);
        let beta = rho_new / rho_old;

        // p = r + beta * p
        // => p = beta * p + r (in-place)
        p.scale_mut(beta);
        p += &r;

        rho_old = rho_new;
    }
    x
}

/// Helper for Sparse Matrix - Vector multiplication: y = A * x
/// avoiding per-call allocation
fn spmv_csr(a: &CsrMatrix<f64>, x: &DVector<f64>, y: &mut DVector<f64>) {
    // Access raw CSR structures
    let row_offsets = a.row_offsets();
    let col_indices = a.col_indices();
    let values = a.values();

    // y must handle the result, so we overwrite it
    // Iterate over rows
    for (row_idx, row_range) in row_offsets.windows(2).enumerate() {
        let start = row_range[0];
        let end = row_range[1];
        let mut sum = 0.0;

        for i in start..end {
            let col_idx = col_indices[i];
            let val = values[i];
            // x is a DVector, indexing works
            sum += val * x[col_idx];
        }
        y[row_idx] = sum;
    }
}
